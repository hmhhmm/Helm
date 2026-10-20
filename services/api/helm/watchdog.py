"""Watchdog (CODE). Reads the audit log, checks drift, tests attacks; can pull the kill switch."""
from dataclasses import dataclass
from datetime import date

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.agents import reader
from helm.audit import append, now_iso, verify_chain
from helm.engine.policy import PolicyContext, ProposalIn, decide
from helm.models import Alert, Balance, CashRange, Decision, Instruction, Receipt, Rules
from helm.seed import docs


@dataclass
class WatchdogReport:
    alerts: list[dict]
    checks: dict


def _alert(session: Session, level: str, message: str) -> dict:
    exists = session.execute(select(Alert).where(Alert.message == message, Alert.resolved.is_(False))).first()
    if not exists:
        session.add(Alert(ts=now_iso(), level=level, source="watchdog", message=message))
        session.flush()
    return {"level": level, "message": message}


def _engage_kill_switch(session: Session, why: str) -> None:
    rules = session.get(Rules, 1)
    if not rules.kill_switch:
        rules.kill_switch = True
        append(session, "watchdog", "kill_switch.engaged", {"reason": why, "by": "watchdog"})


def attack_selftest(ctx: PolicyContext, today: date) -> dict:
    """Feed a poisoned invoice through Reader and Policy in a dry run. Must never come out ALLOW."""
    raw = docs.bill_doc("Selftest Supplies", "SELFTEST-1", today, today, 48_000, "DEMO-0000-0000", note=docs.MALICIOUS_NOTE)
    out = reader.run(reader.ReaderInput(doc_id="selftest", kind="bill", raw_text=raw))
    p = ProposalIn("selftest", "pay_bill", out.counterparty, out.bank_account or "?", out.amount, 0, "supplier", out.reference, out.quarantined)
    scratch = PolicyContext(rules=ctx.rules, today=ctx.today, scen=ctx.scen, registry=ctx.registry, paid_refs=set(ctx.paid_refs), receipts=list(ctx.receipts),
                            reserve_balance=ctx.reserve_balance, sent_by_day=dict(ctx.sent_by_day), committed_by_day=dict(ctx.committed_by_day), committed=ctx.committed.copy())
    verdict = decide(p, scratch, set()).verdict
    return {"quarantined": out.quarantined, "verdict": verdict, "passed": out.quarantined and verdict in ("ESCALATE", "DENY")}


def run(session: Session, today: date, ctx: PolicyContext, previous_range: CashRange | None) -> WatchdogReport:
    alerts: list[dict] = []
    checks: dict = {}

    chain = verify_chain(session)
    checks["audit_chain"] = chain
    if not chain["ok"]:
        alerts.append(_alert(session, "critical", f"Audit log was altered (row {chain['broken_at']}: {chain['reason']}). Kill switch engaged."))
        _engage_kill_switch(session, "audit chain broken")

    # Every accepted payment must trace back to an ALLOW decision.
    unauthorised = 0
    for r, ins in session.execute(
        select(Receipt, Instruction).join(Instruction, Instruction.id == Receipt.instruction_id).where(Receipt.status == "accepted")
    ).all():
        d = session.get(Decision, ins.decision_id)
        if d is None or d.verdict != "ALLOW":
            unauthorised += 1
    checks["unauthorised_payments"] = unauthorised
    if unauthorised:
        alerts.append(_alert(session, "critical", f"{unauthorised} payment(s) left without an ALLOW decision. Kill switch engaged."))
        _engage_kill_switch(session, "payment without ALLOW decision")

    # Forecast drift: was yesterday's range right about today?
    drift = {"checked": False}
    if previous_range is not None:
        days = previous_range.summary.get("days", [])
        managed = previous_range.summary.get("managed") or {}
        if today.isoformat() in days and managed:
            i = days.index(today.isoformat())
            actual = session.get(Balance, (today, "operating"))
            if actual:
                lo, hi = managed["p10"][i], managed["p90"][i]
                inside = lo <= actual.amount <= hi
                drift = {"checked": True, "inside_band": inside, "actual": actual.amount, "p10": lo, "p90": hi}
                if not inside:
                    alerts.append(_alert(session, "warn", f"Forecast drift: the balance on {today.isoformat()} (RM {actual.amount:,.0f}) was outside the forecast's 80% range."))
    checks["forecast_drift"] = drift

    attack = attack_selftest(ctx, today)
    checks["attack_selftest"] = attack
    if not attack["passed"]:
        alerts.append(_alert(session, "critical", "Attack self-test failed: a poisoned invoice was not stopped. Kill switch engaged."))
        _engage_kill_switch(session, "attack self-test failed")

    append(session, "watchdog", "watchdog.checked", {
        "chain_ok": chain["ok"], "rows": chain["checked"], "unauthorised_payments": unauthorised,
        "attack_selftest": attack["passed"], "drift": drift.get("inside_band"),
    })
    return WatchdogReport(alerts, checks)
