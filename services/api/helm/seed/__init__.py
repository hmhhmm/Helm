"""Idempotent, deterministic seeding. `python -m helm.seed` resets and reseeds."""
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from sqlalchemy.orm import Session

from helm.audit import append
from helm.ingest import ingest_document
from helm.models import (
    Balance, Bill, Customer, Rules, SimFuture, SimState, SimTruth, Supplier,
)
from helm.seed import docs
from helm.seed.world import (
    AMOUNT_SCALE, EXTRA_INVOICES, ISSUE_OVERRIDES, SOFT_FACTOR, SOFT_FROM, SOFT_TO,
    BILL_OVERRIDES, CUSTOMERS, EIS, EPF, HIST_START, OPENING_TARGET, PAYROLL, PCB, RESERVE_START,
    SIM_END, SOCSO, SST, STATUTORY, SUPPLIERS, TODAY, add_months, month_end, rng, round10,
)


@dataclass
class WInvoice:
    customer_id: str
    customer_name: str
    amount: float
    issued: date
    due: date
    pay_date: date
    id: str = ""
    number: str = ""


@dataclass
class WBill:
    kind: str
    supplier_id: str
    payee: str
    account: str
    amount: float
    issued: date
    due: date
    paid_on: date | None  # only meaningful for history; None = not paid yet
    label: str
    ref: str = ""
    id: str = ""


@dataclass
class World:
    invoices: list[WInvoice] = field(default_factory=list)
    bills: list[WBill] = field(default_factory=list)


def _abbr(name: str) -> str:
    return "".join(w[0] for w in name.replace("&", "").split() if w[0].isalpha()).upper()[:4]


def build_world() -> World:
    r = rng()
    w = World()

    # --- invoices (money in) ------------------------------------------------
    for c in CUSTOMERS:
        dates: list[date] = []
        gen_start = HIST_START - timedelta(days=110)  # so receipts in the window are complete
        if c.day_of_month:
            d = date(gen_start.year, gen_start.month, c.day_of_month)
            while d <= SIM_END:
                if d >= gen_start:
                    dates.append(d)
                d = add_months(d, 1).replace(day=c.day_of_month)
        else:
            interval = 365 / c.per_year
            d = gen_start + timedelta(days=int(r.integers(0, int(interval))))
            while d <= SIM_END:
                dates.append(d)
                d += timedelta(days=max(10, int(round(interval * (1 + r.normal(0, 0.15))))))
        for d in dates:
            amount = round10(AMOUNT_SCALE * c.amt_mu * float(np.exp(r.normal(0, c.amt_sigma))))
            lateness = int(round(r.normal(c.delay_mu, c.delay_sd)))
            due = d + timedelta(days=c.terms)
            pay = max(due + timedelta(days=lateness), d + timedelta(days=3))
            w.invoices.append(WInvoice(c.id, c.name, amount, d, due, pay))
    for inv in w.invoices:
        if SOFT_FROM <= inv.issued <= SOFT_TO and inv.customer_id not in ("c01", "c02"):
            inv.amount = round10(inv.amount * SOFT_FACTOR)
    cust_by_id = {c.id: c for c in CUSTOMERS}
    for cid, issued, amount in EXTRA_INVOICES:
        c = cust_by_id[cid]
        due = issued + timedelta(days=c.terms)
        w.invoices.append(WInvoice(cid, c.name, amount, issued, due, due + timedelta(days=int(c.delay_mu))))
    w.invoices.sort(key=lambda i: (i.issued, i.customer_id))
    for n, inv in enumerate(w.invoices, 1):
        inv.id = f"inv_{n:04d}"
        inv.number = f"WP-{inv.issued.year}-{n:04d}"

    # --- supplier bills (money out) -----------------------------------------
    start_month = date(2025, 9, 1)
    for s in SUPPLIERS:
        for k in range(0, 22):
            first = add_months(start_month, k)
            if (k - s.offset) % s.every != 0:
                continue
            jitter = 0 if s.fixed else int(r.integers(-2, 3))
            issued = first.replace(day=s.issue_day) + timedelta(days=jitter)
            issued = ISSUE_OVERRIDES.get((s.id, issued.year, issued.month), issued)
            amount = s.mean if s.sd_frac == 0 else round10(s.mean * float(np.exp(r.normal(0, s.sd_frac))))
            amount = BILL_OVERRIDES.get((s.id, issued.year, issued.month), amount)
            due = issued + timedelta(days=s.terms)
            if due < HIST_START or issued > SIM_END:
                continue
            slip = int(r.choice([-1, 0, 0, 0, 1, 2]))
            paid = due + timedelta(days=slip)
            w.bills.append(WBill("supplier", s.id, s.name, s.account, amount, issued, due, paid, s.name))
    # --- statutory calendar and payroll -------------------------------------
    reg = {g[0]: g for g in STATUTORY}
    m = date(2025, 11, 1)
    while m <= SIM_END + timedelta(days=60):
        prev = add_months(m, -1)
        tag = f"{m:%b %Y}"
        for gid, amount, label in [
            ("g01", EPF, f"EPF contribution · {prev:%b %Y} payroll"),
            ("g02", SOCSO, f"SOCSO · {prev:%b %Y} payroll"),
            ("g03", EIS, f"EIS · {prev:%b %Y} payroll"),
            ("g04", PCB, f"PCB (LHDN) · {prev:%b %Y} payroll"),
        ]:
            due = m.replace(day=15)
            w.bills.append(WBill("statutory", gid, reg[gid][1], reg[gid][2], amount, due - timedelta(days=10), due, due, label))
        if m.month in (1, 3, 5, 7, 9, 11):
            due = month_end(m)
            w.bills.append(WBill("statutory", "g05", reg["g05"][1], reg["g05"][2], SST, due - timedelta(days=20), due, due, f"SST · bi-monthly to {prev:%b %Y}"))
        due = m.replace(day=28)
        w.bills.append(WBill("payroll", "g06", reg["g06"][1], reg["g06"][2], PAYROLL, due - timedelta(days=10), due, due, f"Payroll · {tag}"))
        m = add_months(m, 1)
    w.bills = [b for b in w.bills if HIST_START <= b.due <= SIM_END + timedelta(days=45)]
    w.bills.sort(key=lambda b: (b.due, b.supplier_id))
    counts: dict[str, int] = {}
    for n, b in enumerate(w.bills, 1):
        b.id = f"bill_{n:04d}"
        key = f"{_abbr(b.payee)}-{b.issued:%y%m}"
        counts[key] = counts.get(key, 0) + 1
        b.ref = f"{key}-{counts[key]:02d}"
    return w


def seed_database(session: Session) -> dict:
    """Write the world into an empty database. Call helm.db.reset_db() first for a clean slate."""
    w = build_world()

    for c in CUSTOMERS:
        session.add(Customer(id=c.id, name=c.name, terms_days=c.terms, tone=c.tone))
    for s in SUPPLIERS:
        session.add(Supplier(id=s.id, name=s.name, kind="supplier", terms_days=s.terms, account_ref=s.account))
    for gid, name, acct, kind in STATUTORY:
        session.add(Supplier(id=gid, name=name, kind=kind, terms_days=0, account_ref=acct))
    session.flush()

    cust_name = {c.id: c for c in CUSTOMERS}
    receipts: list[tuple[date, float]] = []
    payments: list[tuple[date, float]] = []
    n_hist_inv = n_open_inv = n_hist_bill = n_open_bill = n_future = 0

    for inv in w.invoices:
        raw = docs.invoice_doc(inv.customer_name, inv.number, inv.issued, inv.due, inv.amount)
        if inv.issued > TODAY:
            session.add(SimFuture(
                id=f"fut_{inv.id}", kind="invoice", arrive_on=inv.issued, raw_text=raw,
                truth_pay_date=inv.pay_date, meta={"record_id": inv.id},
            ))
            n_future += 1
        elif inv.pay_date <= TODAY:
            from helm.models import Invoice
            session.add(Invoice(
                id=inv.id, number=inv.number, customer_id=inv.customer_id, amount=inv.amount,
                issued=inv.issued, due=inv.due, paid_on=inv.pay_date, source="ledger",
            ))
            receipts.append((inv.pay_date, inv.amount))
            n_hist_inv += 1 if inv.issued >= HIST_START else 0
        else:
            ingest_document(session, doc_id=f"doc_{inv.id}", kind="invoice", received_on=inv.issued,
                            raw_text=raw, source="ledger", record_id=inv.id, audit=False)
            session.add(SimTruth(invoice_id=inv.id, pay_date=inv.pay_date))
            n_open_inv += 1

    for b in w.bills:
        if b.kind != "supplier":
            paid = b.due if b.due <= TODAY else None
            session.add(Bill(
                id=b.id, kind=b.kind, supplier_id=b.supplier_id, payee=b.payee, ref=b.ref,
                account_ref=b.account, label=b.label, amount=b.amount, issued=b.issued, due=b.due,
                paid_on=paid, source="statutory_calendar",
            ))
            if paid:
                payments.append((paid, b.amount))
            continue
        raw = docs.bill_doc(b.payee, b.ref, b.issued, b.due, b.amount, b.account)
        if b.issued > TODAY:
            session.add(SimFuture(
                id=f"fut_{b.id}", kind="bill", arrive_on=b.issued, raw_text=raw, truth_pay_date=None,
                meta={"record_id": b.id},
            ))
            n_future += 1
        elif b.paid_on and b.paid_on <= TODAY:
            session.add(Bill(
                id=b.id, kind="supplier", supplier_id=b.supplier_id, payee=b.payee, ref=b.ref,
                account_ref=b.account, label=f"{b.payee} · {b.ref}", amount=b.amount, issued=b.issued,
                due=b.due, paid_on=b.paid_on, source="ledger",
            ))
            payments.append((b.paid_on, b.amount))
            n_hist_bill += 1
        else:
            ingest_document(session, doc_id=f"doc_{b.id}", kind="bill", received_on=b.issued,
                            raw_text=raw, source="supplier_email", record_id=b.id, audit=False)
            n_open_bill += 1
    session.flush()

    # Daily operating balance, back-solved so that TODAY lands exactly on the persona's RM 85,000.
    delta: dict[date, float] = {}
    for d, a in receipts:
        delta[d] = delta.get(d, 0.0) + a
    for d, a in payments:
        delta[d] = delta.get(d, 0.0) - a
    total = sum(v for d, v in delta.items() if HIST_START <= d <= TODAY)
    bal = OPENING_TARGET - total
    d = HIST_START
    while d <= TODAY:
        bal += delta.get(d, 0.0)
        session.add(Balance(on=d, account="operating", amount=round(bal, 2)))
        d += timedelta(days=1)
    session.add(Balance(on=TODAY, account="reserve", amount=RESERVE_START))

    session.add(Rules(
        id=1, min_balance=20_000, risk_tolerance=0.10, approval_limit=25_000,
        protected_payees=["Sewa Premis Klang", "Bekalan Elektrik Demo", "Insurans Perniagaan Selamat"],
        kill_switch=False, horizon_days=90,
    ))
    session.add(SimState(id=1, today=TODAY, flags={}))
    append(session, "system", "seed.created", {
        "note": "Synthetic demo data", "seed": 2026, "history_invoices": n_hist_inv, "open_invoices": n_open_inv,
        "history_bills": n_hist_bill, "open_bills": n_open_bill, "future_documents": n_future,
    })
    session.flush()
    return {
        "history_invoices": n_hist_inv, "open_invoices": n_open_inv, "history_bills": n_hist_bill,
        "open_bills": n_open_bill, "future_documents": n_future,
    }
