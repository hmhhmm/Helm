"""Facts (database) -> ForecastInput. Reads facts only; never the hidden simulation tables."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.forecast.montecarlo import BillF, ForecastInput, InvF
from helm.models import Balance, Bill, Customer, Invoice, Supplier


def balance_on(session: Session, on: date, account: str = "operating") -> float:
    row = session.execute(
        select(Balance).where(Balance.account == account, Balance.on <= on).order_by(Balance.on.desc()).limit(1)
    ).scalar_one_or_none()
    return row.amount if row else 0.0


def build_input(
    session: Session, today: date, horizon: int = 90, *, as_of: date | None = None,
    extra_delay: dict[str, int] | None = None, skip_bills: set[str] | None = None, n_paths: int = 1000,
) -> ForecastInput:
    """as_of=None means 'now'. With as_of set, builds the snapshot of what was known on that day,
    which is how the forecast track record is back-tested honestly."""
    cutoff = as_of or today
    invoices = []
    for i in session.execute(select(Invoice)).scalars():
        if i.issued > cutoff:
            continue
        paid = i.paid_on if (i.paid_on and i.paid_on <= cutoff) else None
        invoices.append(InvF(i.id, i.customer_id, i.amount, i.issued, i.due, paid, 0 if as_of else i.late_signal_days))
    bills = []
    for b in session.execute(select(Bill)).scalars():
        if b.quarantined:
            continue
        if b.kind == "supplier" and b.issued > cutoff:
            continue  # not received yet
        paid = b.paid_on if (b.paid_on and b.paid_on <= cutoff) else None
        bills.append(BillF(b.id, b.kind, b.supplier_id, b.payee, b.amount, b.issued, b.due, paid))
    cust = {c.id: c.terms_days for c in session.execute(select(Customer)).scalars()}
    sup = {s.id: s.terms_days for s in session.execute(select(Supplier)).scalars()}
    return ForecastInput(
        today=cutoff, horizon=horizon, start_balance=balance_on(session, cutoff), invoices=invoices,
        bills=bills, customer_terms=cust, supplier_terms=sup, n_paths=n_paths,
        extra_delay=extra_delay or {}, skip_bills=frozenset(skip_bills or ()),
    )
