"""Executor (CODE). Sends approved payments to the Demo bank with a scoped, expiring key.

It acts only on decisions the Policy Engine marked ALLOW, re-reads the kill switch immediately before
every instruction, and never reads agent output directly.
"""
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.audit import append, now_iso
from helm.bank import service as bank
from helm.forecast.service import balance_on
from helm.models import Balance, Bill, Decision, Instruction, Proposal, Receipt, Rules


def latest_decision(session: Session, proposal_id: str) -> Decision | None:
    return session.execute(
        select(Decision).where(Decision.proposal_id == proposal_id).order_by(Decision.id.desc()).limit(1)
    ).scalar_one_or_none()


def _apply_balance(session: Session, today: date, account: str, delta: float) -> None:
    row = session.get(Balance, (today, account))
    if row is None:
        session.add(Balance(on=today, account=account, amount=round(balance_on(session, today, account) + delta, 2)))
    else:
        row.amount = round(row.amount + delta, 2)
    session.flush()


def execute_one(session: Session, proposal: Proposal, decision: Decision, today: date) -> Receipt | None:
    """Release one ALLOWed proposal. Returns the receipt, or None if the executor refused."""
    rules = session.get(Rules, 1)
    session.refresh(rules)
    if rules.kill_switch:
        append(session, "executor", "executor.refused", {"proposal_id": proposal.id, "reason": "kill switch on"})
        return None
    if decision.verdict != "ALLOW":
        append(session, "executor", "executor.refused", {"proposal_id": proposal.id, "reason": f"verdict is {decision.verdict}"})
        return None

    ins_id = "ins_" + uuid.uuid4().hex[:10]
    payload = {
        "proposal_id": proposal.id, "payee": proposal.payee, "to_account": proposal.account_ref,
        "amount": proposal.amount, "currency": "MYR", "execute_on": today.isoformat(), "kind": proposal.kind,
    }
    session.add(Instruction(id=ins_id, decision_id=decision.id, proposal_id=proposal.id, payload=payload, created_at=now_iso()))
    key = bank.mint_key(to_account=proposal.account_ref, max_amount=proposal.amount, scope=proposal.id)
    from_acct = "reserve" if proposal.kind == "top_up" else "operating"
    result = bank.submit(session, key=key, instruction_id=ins_id, from_account=from_acct,
                         to_account=proposal.account_ref, amount=proposal.amount, scope=proposal.id)
    rcpt = Receipt(
        id=result["receipt_id"], instruction_id=ins_id, proposal_id=proposal.id, status=result["status"],
        payload=result, sim_date=today, created_at=now_iso(),
    )
    session.add(rcpt)
    if result["status"] == "accepted":
        if proposal.kind == "pay_bill":
            _apply_balance(session, today, "operating", -proposal.amount)
            bill = session.get(Bill, proposal.bill_id)
            if bill:
                bill.paid_on = today
        elif proposal.kind == "sweep":
            _apply_balance(session, today, "operating", -proposal.amount)
            _apply_balance(session, today, "reserve", proposal.amount)
        elif proposal.kind == "top_up":
            _apply_balance(session, today, "reserve", -proposal.amount)
            _apply_balance(session, today, "operating", proposal.amount)
        proposal.status = "executed"
    append(session, "executor", "payment.sent" if result["status"] == "accepted" else "payment.rejected", {
        "proposal_id": proposal.id, "instruction_id": ins_id, "receipt_id": rcpt.id, "payee": proposal.payee,
        "amount": proposal.amount, "bank": "Demo bank", "status": result["status"], "reason": result["reason"],
    })
    session.flush()
    return rcpt


def execute_due(session: Session, today: date) -> list[Receipt]:
    """Pay every pay_bill proposal whose latest decision is ALLOW and whose release date has come."""
    out: list[Receipt] = []
    proposals = session.execute(
        select(Proposal).where(Proposal.status == "open", Proposal.kind == "pay_bill").order_by(Proposal.proposed_date, Proposal.id)
    ).scalars().all()
    for p in proposals:
        d = latest_decision(session, p.id)
        if d and d.verdict == "ALLOW" and d.release_on and d.release_on <= today:
            r = execute_one(session, p, d, today)
            if r:
                out.append(r)
            elif session.get(Rules, 1).kill_switch:
                break  # one refusal is enough to stop the run
    return out
