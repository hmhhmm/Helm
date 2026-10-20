"""Owner entered payments. A payee Helm has not paid before is a new payee, so it waits for the owner's approval."""
import hashlib
import uuid

from sqlalchemy.orm import Session

from helm import pipeline
from helm.audit import append
from helm.models import Bill
from helm.rules_view import sim_today


def enter_payment(session: Session, payee: str, amount: float, reference: str = "") -> str:
    """Adds a bill due today and runs the gate. Returns the proposal id."""
    today = sim_today(session)
    payee = payee.strip()
    ref = reference.strip() or "LIVE-" + uuid.uuid4().hex[:6].upper()
    b = Bill(id="bl_" + uuid.uuid4().hex[:8], kind="supplier", supplier_id=None, payee=payee, ref=ref,
             account_ref="ACC-" + hashlib.sha256(payee.lower().encode()).hexdigest()[:10].upper(),
             label=payee, amount=round(amount, 2), issued=today, due=today, source="owner_entry", confidence=1.0)
    session.add(b)
    append(session, "human", "owner.entered_payment", {"bill_id": b.id, "payee": payee, "amount": b.amount, "ref": ref})
    pipeline.run_pipeline(session, mode="gate", trigger=f"owner entered {b.id}")
    return f"p_{b.id}"
