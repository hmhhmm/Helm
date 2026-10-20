"""The simulator. Moves a deterministic, hidden world forward and pokes the system.

The world (sim_truth, sim_future) is never read by an agent; it only produces the *evidence* that
agents later read: bank-feed receipts, new documents, customer messages.
"""
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from helm import executor
from helm.audit import append
from helm.executor import _apply_balance
from helm.forecast.service import balance_on
from helm.ingest import ingest_document
from helm.models import Balance, CashRange, Customer, Decision, Invoice, Proposal, SimFuture, SimState, SimTruth
from helm.pipeline import latest_decisions, run_pipeline
from helm.seed import docs
from helm.fmt import fdate, rm

LATE_DAYS = 20
MALICIOUS_PAYEE = "Nexus Trading Supplies"
MALICIOUS_ACCOUNT = "MY-9999-0042"


def _set_flag(state: SimState, key: str, value) -> None:
    state.flags = {**state.flags, key: value}
    flag_modified(state, "flags")


def _add_unreported(state: SimState, doc_id: str) -> None:
    _set_flag(state, "inbox_unreported", [*state.flags.get("inbox_unreported", []), doc_id])


def snapshot(session: Session) -> dict:
    cr = session.execute(select(CashRange).order_by(CashRange.created_at.desc()).limit(1)).scalar_one()
    s = cr.summary
    u = s["unmanaged"]
    lo, hi = 20, 70
    width = float(np.mean(np.array(u["p90"][lo:hi]) - np.array(u["p10"][lo:hi])))
    decisions = {pid: (d.verdict, d.release_on.isoformat() if d.release_on else None) for pid, d in latest_decisions(session).items()}
    return {"band_width": width, "low": s["low_unmanaged"], "p_ok_unmanaged": s["p_ok_unmanaged"], "p_ok_managed": s["p_ok_managed"], "decisions": decisions}


def _diff(session: Session, before: dict, after: dict) -> list[dict]:
    flips = []
    for pid, (v1, r1) in after["decisions"].items():
        v0, r0 = before["decisions"].get(pid, (None, None))
        if (v0, r0) != (v1, r1) and v0 is not None:
            p = session.get(Proposal, pid)
            if p and p.kind == "pay_bill":
                flips.append({"proposal_id": pid, "payee": p.payee, "amount": p.amount, "from": v0, "to": v1, "release_from": r0, "release_to": r1})
    return flips


# ------------------------------------------------------------------------------ customer pays late
def customer_late(session: Session) -> dict:
    state = session.get(SimState, 1)
    if state.flags.get("late_applied"):
        return {"applied": False, "message": "Already applied. Use Reset demo to try it again.", "flips": []}
    big = session.execute(
        select(Invoice).where(Invoice.paid_on.is_(None)).order_by(Invoice.amount.desc()).limit(1)
    ).scalar_one()
    customer = session.get(Customer, big.customer_id)
    before = snapshot(session)

    # What Helm learns: a message from the customer. What the world does: it really pays 20 days later.
    big.late_signal_days = LATE_DAYS
    big.source = "customer_message"
    truth = session.get(SimTruth, big.id)
    truth.pay_date = truth.pay_date + timedelta(days=LATE_DAYS)
    _set_flag(state, "late_applied", True)
    append(session, "simulator", "customer.late_notice", {
        "customer": customer.name, "invoice": big.number, "amount": big.amount, "days_later": LATE_DAYS,
        "note": "A customer says they will pay 20 days late.",
    })
    run_pipeline(session, mode="full", trigger="customer_late")
    after = snapshot(session)
    flips = _diff(session, before, after)
    return {
        "applied": True, "customer": customer.name, "invoice": big.number, "amount": big.amount, "days": LATE_DAYS,
        "band_width_before": round(before["band_width"]), "band_width_after": round(after["band_width"]),
        "low_before": before["low"], "low_after": after["low"],
        "p_ok_before": before["p_ok_unmanaged"], "p_ok_after": after["p_ok_unmanaged"],
        "flips": flips,
        "message": (f"{customer.name} will pay {rm(big.amount)} {LATE_DAYS} days late. The forecast band widened and "
                    f"{len(flips)} payment(s) changed."),
    }


# ------------------------------------------------------------------------------ malicious invoice
def inject_malicious(session: Session) -> dict:
    state = session.get(SimState, 1)
    today = state.today
    existing = session.execute(
        select(Proposal).where(Proposal.payee == MALICIOUS_PAYEE, Proposal.status == "open")
    ).scalars().first()
    if existing:
        d = executor.latest_decision(session, existing.id)
        return {"injected": False, "proposal_id": existing.id, "verdict": d.verdict if d else None,
                "message": "A suspicious invoice is already waiting for you."}
    n = (state.flags.get("malicious_count", 0)) + 1
    _set_flag(state, "malicious_count", n)
    rec, doc_id = f"bill_mal_{n}", f"doc_mal_{n}"
    raw = docs.bill_doc(MALICIOUS_PAYEE, f"NTS-{today:%y%m}-{n:04d}", today, today, 48_000, MALICIOUS_ACCOUNT, note=docs.MALICIOUS_NOTE)
    doc = ingest_document(session, doc_id=doc_id, kind="bill", received_on=today, raw_text=raw,
                          source="supplier_email", record_id=rec)
    _add_unreported(state, doc_id)
    before_balance = balance_on(session, today)
    run_pipeline(session, mode="full", trigger="malicious_invoice")
    p = session.get(Proposal, f"p_{rec}")
    d = executor.latest_decision(session, p.id)
    return {
        "injected": True, "proposal_id": p.id, "doc_id": doc_id, "verdict": d.verdict, "why": d.why,
        "quarantined": doc.quarantined, "flags": doc.flags,
        "money_moved": round(before_balance - balance_on(session, today), 2) if d.verdict != "ESCALATE" else 0.0,
        "message": "Helm read the invoice as data, ignored the instruction inside it, and asked you before paying.",
    }


# ------------------------------------------------------------------------------ advance time
def _new_day_balances(session: Session, day: date) -> None:
    for acct in ("operating", "reserve"):
        if session.get(Balance, (day, acct)) is None:
            session.add(Balance(on=day, account=acct, amount=balance_on(session, day - timedelta(days=1), acct)))
    session.flush()


def _arrivals(session: Session, state: SimState, day: date) -> int:
    n = 0
    for f in session.execute(select(SimFuture).where(SimFuture.arrive_on <= day).order_by(SimFuture.arrive_on, SimFuture.id)).scalars().all():
        rec = f.meta["record_id"]
        ingest_document(session, doc_id=f"doc_{rec}", kind=f.kind, received_on=f.arrive_on, raw_text=f.raw_text,
                        source="ledger" if f.kind == "invoice" else "supplier_email", record_id=rec)
        if f.kind == "invoice" and f.truth_pay_date:
            session.add(SimTruth(invoice_id=rec, pay_date=f.truth_pay_date))
        _add_unreported(state, f"doc_{rec}")
        session.delete(f)
        n += 1
    session.flush()
    return n


def _receipts_in(session: Session, day: date) -> float:
    total = 0.0
    rows = session.execute(
        select(Invoice, SimTruth).join(SimTruth, SimTruth.invoice_id == Invoice.id)
        .where(Invoice.paid_on.is_(None), SimTruth.pay_date <= day).order_by(SimTruth.pay_date, Invoice.id)
    ).all()
    for inv, _ in rows:
        inv.paid_on = day
        _apply_balance(session, day, "operating", inv.amount)
        total += inv.amount
        cust = session.get(Customer, inv.customer_id)
        append(session, "bank_feed", "receipt.in", {"invoice": inv.number, "customer": cust.name, "amount": inv.amount, "date": day.isoformat()})
    session.flush()
    return total


def _release_due(session: Session, day: date) -> bool:
    decs = latest_decisions(session)
    for p in session.execute(select(Proposal).where(Proposal.status == "open", Proposal.kind == "pay_bill")).scalars():
        d = decs.get(p.id)
        if d and d.verdict in ("ALLOW", "HOLD") and d.release_on and d.release_on <= day:
            return True
    return False


def advance_week(session: Session) -> dict:
    state = session.get(SimState, 1)
    start = state.today
    before = snapshot(session)
    bal0 = balance_on(session, start)
    received = 0.0
    docs_in = 0
    sent = 0
    for _ in range(7):
        day = state.today + timedelta(days=1)
        state.today = day
        session.flush()
        _new_day_balances(session, day)
        docs_in += _arrivals(session, state, day)
        received += _receipts_in(session, day)
        if _release_due(session, day):
            from helm.models import Receipt
            n0 = len(session.execute(select(Receipt)).scalars().all())
            run_pipeline(session, mode="gate", trigger=f"release_due {day.isoformat()}", execute=True)
            sent += len(session.execute(select(Receipt)).scalars().all()) - n0
    run_pipeline(session, mode="full", trigger="advance_week", execute=True)
    after = snapshot(session)
    bal1 = balance_on(session, state.today)
    append(session, "simulator", "time.advanced", {"from": start.isoformat(), "to": state.today.isoformat(), "received": round(received), "documents": docs_in})
    return {
        "from": start.isoformat(), "to": state.today.isoformat(), "received": round(received), "paid": sent,
        "new_documents": docs_in, "balance_before": round(bal0), "balance_after": round(bal1),
        "flips": _diff(session, before, after),
        "message": f"Advanced to {fdate(state.today)}: {rm(received)} came in, {sent} payment(s) sent, {docs_in} new document(s) read.",
    }
