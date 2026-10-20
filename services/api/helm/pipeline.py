"""Orchestration: a plain Python pipeline (the LangGraph wrapper lives in helm.graph).

Agents hand off through typed database records in a fixed order:

  Reader -> facts -> Forecaster -> cash_range -> Scheduler -> bill_plan -> proposals
  Collections (facts) -> chase_ideas        Treasury (bill_plan) -> proposals
  proposals -> Policy Engine -> decisions -> Human Review (ESCALATE) -> Executor -> receipts -> Explainer
  Watchdog reads the audit log after every run.

Two modes: "full" runs everything; "gate" re-forecasts and re-decides only (used when a payment's
release date arrives, so a payment is always re-checked against fresh cash on the day it would go).
"""
import statistics
import time
import zlib
from datetime import date, timedelta

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from helm import executor, watchdog
from helm.agents import collections as collections_agent
from helm.agents import explainer, forecaster, scheduler, treasury
from helm.audit import append, now_iso
from helm.engine.policy import Decision as PDecision
from helm.engine.policy import Payee, PolicyContext, ProposalIn, Receipt as PReceipt, evaluate_all
from helm.forecast.montecarlo import ForecastResult
from helm.forecast.service import balance_on, build_input
from helm.models import (
    AgentRun, AgentStep, BillPlan, Bill, CashRange, ChaseIdea, Customer, Decision, Invoice, Proposal,
    Receipt, SimState, Supplier,
)
from helm.rules_view import RulesView, load_rules, sim_today

NODES = ["reader", "forecaster", "collections", "scheduler", "treasury", "policy", "human", "executor", "explainer", "watchdog"]
RESERVE_ACCOUNT = "RESERVE-DEMO"


# ----------------------------------------------------------------------------- helpers
def _next_run_id(session: Session) -> str:
    return f"run_{(session.scalar(select(func.count(AgentRun.id))) or 0) + 1:04d}"


def _record(session: Session, run_id: str, node: str, status: str, t0: float, summary: str, detail: dict | None = None) -> None:
    session.add(AgentStep(run_id=run_id, node=node, status=status, ms=int((time.perf_counter() - t0) * 1000), summary=summary, detail=detail or {}))
    session.flush()


def _registry(session: Session) -> dict[str, Payee]:
    amounts: dict[str, list[float]] = {}
    for b in session.execute(select(Bill).where(Bill.paid_on.is_not(None), Bill.kind == "supplier")).scalars():
        if b.supplier_id:
            amounts.setdefault(b.supplier_id, []).append(b.amount)
    reg = {}
    for s in session.execute(select(Supplier)).scalars():
        typical = statistics.median(amounts[s.id]) if amounts.get(s.id) else None
        reg[s.name] = Payee(s.name, s.account_ref, s.kind, typical)
    return reg


def _open_bills(session: Session, today: date, horizon: int) -> list[Bill]:
    out = []
    for b in session.execute(select(Bill).where(Bill.paid_on.is_(None)).order_by(Bill.due, Bill.id)).scalars():
        if b.due > today + timedelta(days=horizon):
            continue
        if b.kind == "supplier" and b.issued > today:
            continue
        out.append(b)
    return out


def _compress(cumbase: np.ndarray) -> bytes:
    return zlib.compress(cumbase.astype(np.float32).tobytes(), 3)


def load_paths(blob: bytes, shape: tuple[int, int]) -> np.ndarray:
    return np.frombuffer(zlib.decompress(blob), dtype=np.float32).reshape(shape).astype(np.float64)


def _bands_json(bands: dict[str, np.ndarray]) -> dict:
    return {k: [round(float(x), 0) for x in v] for k, v in bands.items()}


def latest_decisions(session: Session) -> dict[str, Decision]:
    sub = select(func.max(Decision.id)).group_by(Decision.proposal_id)
    rows = session.execute(select(Decision).where(Decision.id.in_(sub))).scalars().all()
    return {d.proposal_id: d for d in rows}


# ----------------------------------------------------------------------------- policy pass
def _upsert_proposals(session: Session, today: date, rules: RulesView, plan: dict[str, tuple[date | None, int]]) -> list[Proposal]:
    out = []
    for b in _open_bills(session, today, rules.horizon_days):
        pid = f"p_{b.id}"
        p = session.get(Proposal, pid)
        plan_date, days_late = plan.get(b.id, (b.due, 0))
        meta = {
            "ref": b.ref, "due": b.due.isoformat(), "bill_kind": b.kind, "quarantined": b.quarantined, "label": b.label,
            "plan_date": plan_date.isoformat() if plan_date else None, "plan_days_late": days_late, "doc_id": b.doc_id,
        }
        if p is None:
            p = Proposal(
                id=pid, kind="pay_bill", bill_id=b.id, payee=b.payee, account_ref=b.account_ref, amount=b.amount,
                proposed_date=max(today, b.due), origin="scheduler", status="open", meta=meta, created_at=now_iso(),
            )
            session.add(p)
        elif p.status == "open":
            p.proposed_date = max(today, b.due)
            p.amount, p.payee, p.account_ref = b.amount, b.payee, b.account_ref
            p.meta = {**p.meta, **meta}
        out.append(p)
    session.flush()
    return out


def _policy_inputs(session: Session, today: date, rules: RulesView, res: ForecastResult, inp) -> tuple[PolicyContext, dict[str, str]]:
    cust = {c.id: c.name for c in session.execute(select(Customer)).scalars()}
    receipts = []
    for i in inp.invoices:
        ex = res.invoice_expect.get(i.id)
        if i.paid_on is None and ex and ex["median"]:
            receipts.append(PReceipt((ex["median"] - today).days, cust.get(i.customer_id, i.customer_id), i.amount))
    paid = {(b.payee, b.ref) for b in session.execute(select(Bill).where(Bill.paid_on.is_not(None))).scalars()}
    sent: dict = {}
    for r, pr in session.execute(select(Receipt, Proposal).join(Proposal, Proposal.id == Receipt.proposal_id)
                                 .where(Receipt.status == "accepted", Proposal.kind == "pay_bill")).all():
        sent[r.sim_date] = sent.get(r.sim_date, 0.0) + pr.amount
    ctx = PolicyContext(
        rules=rules, today=today, scen=res.scen, registry=_registry(session), paid_refs=paid, receipts=receipts,
        reserve_balance=balance_on(session, today, "reserve"), sent_by_day=sent,
    )
    return ctx, cust


def _order(proposals: list[Proposal], today: date) -> list[Proposal]:
    """Statutory first (by due), then on-time suppliers, then bills the Scheduler chose to stretch, then transfers."""
    def key(p: Proposal):
        if p.kind in ("sweep", "top_up"):
            return (3, 0, p.proposed_date, p.id)
        bk = p.meta.get("bill_kind", "supplier")
        if bk in ("statutory", "payroll"):
            return (0, 0, p.proposed_date, p.id)
        due = date.fromisoformat(p.meta["due"])
        plan = p.meta.get("plan_date")
        stretched = plan is None or date.fromisoformat(plan) > due
        return (1, 1 if stretched else 0, p.proposed_date, p.id)
    return sorted(proposals, key=key)


def _to_policy_inputs(p: Proposal, today: date, approved: set[str]) -> ProposalIn:
    idx = max(0, (p.proposed_date - today).days)
    if p.kind == "pay_bill":
        due_idx = max(0, (date.fromisoformat(p.meta["due"]) - today).days)
        return ProposalIn(p.id, "pay_bill", p.payee, p.account_ref, p.amount, idx, p.meta.get("bill_kind", "supplier"),
                          p.meta.get("ref", ""), bool(p.meta.get("quarantined")), p.id in approved, due_idx)
    return ProposalIn(p.id, p.kind, p.payee, p.account_ref, p.amount, idx, "treasury", "", False, p.id in approved, idx)


def _jsonable(x):
    import json
    return json.loads(json.dumps(x, default=float))


def _persist_decision(session: Session, run_id: str, p: Proposal, d: PDecision, prev: Decision | None, today: date) -> str:
    """Insert a new row when the verdict or release date changed; otherwise refresh the trace in place."""
    changed = prev is None or prev.verdict != d.verdict or prev.release_on != d.release_on
    if changed:
        row = Decision(
            run_id=run_id, proposal_id=p.id, verdict=d.verdict, release_on=d.release_on, checks=d.checks, why=d.why,
            why_ms=d.why_ms, p_ok=d.p_ok, consequence=_jsonable(d.consequence), owner_choice=(prev.owner_choice if prev and prev.owner_choice == "approved" else None),
            created_at=now_iso(),
        )
        session.add(row)
        session.flush()
        append(session, "policy", "decision.made" if prev is None else "decision.changed", {
            "proposal_id": p.id, "payee": p.payee, "amount": p.amount, "verdict": d.verdict,
            "previous_verdict": prev.verdict if prev else None, "release_on": d.release_on.isoformat() if d.release_on else None,
            "previous_release_on": prev.release_on.isoformat() if prev and prev.release_on else None, "why": d.why,
        })
        return "changed"
    prev.run_id, prev.checks, prev.why, prev.why_ms, prev.p_ok = run_id, d.checks, d.why, d.why_ms, d.p_ok
    prev.consequence = _jsonable(d.consequence)
    return "same"


def evaluate(session: Session, today: date, rules: RulesView, inp, res: ForecastResult, plan: dict[str, tuple[date | None, int]],
             *, skip_bills: set[str] | None = None, override_dates: dict[str, date] | None = None):
    """Judge every open proposal without saving anything. Used by the pipeline, what-ifs, previews and 'try paying'."""
    treasury_open = session.execute(select(Proposal).where(Proposal.kind.in_(("sweep", "top_up")), Proposal.status == "open")).scalars().all()
    open_props = session.execute(select(Proposal).where(Proposal.status == "open", Proposal.kind == "pay_bill")).scalars().all()
    if skip_bills:
        open_props = [p for p in open_props if p.bill_id not in skip_bills]
    prevs = latest_decisions(session)
    approved = {pid for pid, d in prevs.items() if d.owner_choice == "approved"}
    ctx, _ = _policy_inputs(session, today, rules, res, inp)
    ordered = _order(open_props + list(treasury_open), today)
    inputs = []
    for p in ordered:
        pi = _to_policy_inputs(p, today, approved)
        if override_dates and p.id in override_dates:
            from dataclasses import replace as _r
            pi = _r(pi, proposed_idx=max(0, (override_dates[p.id] - today).days))
        inputs.append(pi)
    return ctx, evaluate_all(inputs, ctx), ordered, prevs


def policy_pass(session: Session, run_id: str, today: date, rules: RulesView, plan: dict[str, tuple[date | None, int]]):
    """Forecast on current facts, then judge and record every open proposal."""
    inp = build_input(session, today, rules.horizon_days)
    res = forecaster.run(forecaster.ForecasterIn(inp)).result
    _upsert_proposals(session, today, rules, plan)
    ctx, decisions, ordered, prevs = evaluate(session, today, rules, inp, res, plan)
    by_id = {p.id: p for p in ordered}
    stats = {"changed": 0, "same": 0, "ALLOW": 0, "HOLD": 0, "ESCALATE": 0, "DENY": 0, "flips": []}
    for d in decisions:
        p = by_id[d.proposal_id]
        prev = prevs.get(p.id)
        outcome = _persist_decision(session, run_id, p, d, prev, today)
        stats[outcome] += 1
        stats[d.verdict] += 1
        if prev and prev.verdict != d.verdict:
            stats["flips"].append({"proposal_id": p.id, "payee": p.payee, "amount": p.amount, "from": prev.verdict, "to": d.verdict,
                                   "release_on": d.release_on.isoformat() if d.release_on else None})
    session.flush()
    return ctx, res, inp, decisions, stats


def range_summary(rules: RulesView, res: ForecastResult, ctx: PolicyContext) -> dict:
    """Quantile bands and headline numbers for a forecast. Pure: no database."""
    scen, B = res.scen, rules.min_balance
    un = res.unmanaged_commit()
    ub, mb = scen.bands(un), scen.bands(ctx.committed)
    p50 = ub["p50"]
    i50 = int(np.argmin(p50[1:])) + 1
    i10 = int(np.argmin(ub["p10"][1:])) + 1
    return {
        "days": [scen.day(i).isoformat() for i in range(scen.horizon + 1)],
        "start": scen.start, "min_balance": B, "required_confidence": rules.required_confidence,
        "unmanaged": _bands_json(ub), "managed": _bands_json(mb),
        "low_unmanaged": {"date": scen.day(i50).isoformat(), "p50": round(float(p50[i50])), "p10": round(float(ub["p10"][i50])),
                          "worst_date": scen.day(i10).isoformat(), "worst": round(float(ub["p10"][i10]))},
        "p_ok_unmanaged": round(scen.p_ok(un, B), 3),
        "p_ok_managed": round(scen.p_ok(ctx.committed, B), 3),
        "managed_low": {"date": scen.day(int(np.argmin(mb["p50"][1:])) + 1).isoformat(), "p50": round(float(mb["p50"][1:].min())),
                        "p10": round(float(mb["p10"][1:].min()))},
        "assumptions": res.assumptions,
        "invoice_expect": {k: {kk: (vv.isoformat() if vv else None) for kk, vv in v.items()} for k, v in res.invoice_expect.items()},
        "shape": [scen.n, scen.horizon + 1],
    }


def _write_cash_range(session: Session, run_id: str, today: date, rules: RulesView, res: ForecastResult, ctx: PolicyContext) -> dict:
    summary = range_summary(rules, res, ctx)
    row = session.get(CashRange, run_id)
    if row is None:
        session.add(CashRange(run_id=run_id, created_at=now_iso(), summary=summary, paths_blob=_compress(res.scen.cumbase)))
    else:
        row.summary = summary
        row.paths_blob = _compress(res.scen.cumbase)
    session.flush()
    old = session.execute(select(CashRange.run_id).order_by(CashRange.created_at.desc()).offset(4)).scalars().all()
    if old:
        session.execute(delete(CashRange).where(CashRange.run_id.in_(old)))
    return summary


# ----------------------------------------------------------------------------- the run
def run_pipeline(session: Session, *, mode: str = "full", trigger: str = "manual", execute: bool = True) -> str:
    today = sim_today(session)
    rules = load_rules(session)
    run_id = _next_run_id(session)
    session.add(AgentRun(id=run_id, ts=now_iso(), sim_date=today, mode=mode, trigger=trigger))
    session.flush()
    state = session.get(SimState, 1)
    previous_range = session.execute(select(CashRange).order_by(CashRange.created_at.desc()).limit(1)).scalar_one_or_none()

    # 0 Reader ------------------------------------------------------------------------
    t = time.perf_counter()
    fresh = list(state.flags.get("inbox_unreported", []))
    if fresh:
        state.flags = {**state.flags, "inbox_unreported": []}
        flag_modified(state, "flags")
    _record(session, run_id, "reader", "ok" if fresh else "skipped", t,
            f"Read {len(fresh)} new document(s)" if fresh else "No new documents", {"docs": fresh})

    # plan from the previous full run, used for ordering in gate mode
    last_plan: dict[str, tuple[date | None, int]] = {}
    prev_plan_run = session.execute(select(BillPlan.run_id).order_by(BillPlan.id.desc()).limit(1)).scalar_one_or_none()
    if prev_plan_run:
        for r in session.execute(select(BillPlan).where(BillPlan.run_id == prev_plan_run)).scalars():
            last_plan[r.bill_id] = (r.plan_date, r.days_late)

    # 1 Forecaster (+ 3 Scheduler) ---------------------------------------------------------
    t = time.perf_counter()
    inp0 = build_input(session, today, rules.horizon_days)
    res0 = forecaster.run(forecaster.ForecasterIn(inp0)).result
    un0 = res0.unmanaged_commit()
    low_i = int(np.argmin(res0.scen.bands(un0)["p50"][1:])) + 1
    _record(session, run_id, "forecaster", "ok", t,
            f"{res0.scen.n} paths over {rules.horizon_days} days; chance of staying above RM {rules.min_balance:,.0f} if every bill is paid on its due date: {res0.scen.p_ok(un0, rules.min_balance):.0%}",
            {"low_point": res0.scen.day(low_i).isoformat(), "paths": res0.scen.n})

    plan = dict(last_plan)
    if mode == "full":
        t = time.perf_counter()
        # Collections
        cust_rows = session.execute(select(Customer)).scalars().all()
        open_inv = session.execute(select(Invoice).where(Invoice.paid_on.is_(None))).scalars().all()
        views = []
        for c in cust_rows:
            mine = [i for i in open_inv if i.customer_id == c.id]
            if not mine:
                continue
            delays = [(i.paid_on - i.due).days for i in inp0.invoices if i.customer_id == c.id and i.paid_on]
            views.append(collections_agent.CustomerView(
                c.id, c.name, c.tone, (sum(delays) / len(delays)) if delays else 0.0,
                [collections_agent.OpenInvoice(i.id, i.number, i.amount, i.due,
                                               date.fromisoformat(res0.invoice_expect[i.id]["median"].isoformat()) if res0.invoice_expect.get(i.id, {}).get("median") else None)
                 for i in mine],
            ))
        cout = collections_agent.run(collections_agent.CollectionsIn(inp0, views, lambda r: r.unmanaged_commit(), today, rules.min_balance))
        session.execute(delete(ChaseIdea))
        for c in cout.ideas:
            session.add(ChaseIdea(run_id=run_id, customer_id=c.customer_id, rank=c.rank, effect_rm=c.effect_rm, amount_open=c.amount_open,
                                  invoice_ids=c.invoice_ids, tone=c.tone, why=c.why, draft_en=c.draft_en, draft_ms=c.draft_ms))
        _record(session, run_id, "collections", "ok", t, f"Ranked {len(cout.ideas)} customers by effect on your low point",
                {"top": cout.ideas[0].customer_id if cout.ideas else None})

        t = time.perf_counter()
        weights = {}
        name_of = {b.id: b.payee for b in session.execute(select(Bill).where(Bill.paid_on.is_(None))).scalars()}
        for c in res0.candidates:
            if name_of.get(c.bill_id) in rules.protected_payees:
                weights[c.bill_id] = 2
        sout = scheduler.run(scheduler.SchedulerIn(res0.candidates, res0.scen, rules.min_balance, rules.risk_tolerance, weights)).plan
        session.execute(delete(BillPlan))
        plan = {}
        for rank, c in enumerate(sorted(res0.candidates, key=lambda c: (sout.items[c.bill_id].plan_idx if sout.items[c.bill_id].plan_idx is not None else 999, c.due_idx)), 1):
            it = sout.items[c.bill_id]
            pdate = res0.scen.day(it.plan_idx) if it.plan_idx is not None else None
            due = res0.scen.day(c.due_idx)
            plan[c.bill_id] = (pdate, it.days_late)
            note = ("on time" if it.days_late == 0 else
                    f"{it.days_late} days after due" if pdate else "needs more cash than delays alone can free")
            session.add(BillPlan(run_id=run_id, bill_id=c.bill_id, rank=rank, due=due, plan_date=pdate, days_late=it.days_late, note=note))
        late_n = sum(1 for v in sout.items.values() if v.days_late > 0)
        _record(session, run_id, "scheduler", "ok", t,
                f"CP-SAT ({sout.status}, {sout.scenarios} scenarios): {len(sout.items) - late_n} bills on time, {late_n} stretched",
                {"status": sout.status})
    else:
        for n in ("collections", "scheduler", "treasury"):
            _record(session, run_id, n, "skipped", time.perf_counter(), "Not needed for a gate check")

    # Treasury ---------------------------------------------------------------------------
    if mode == "full":
        t = time.perf_counter()
        plan_commit = np.zeros(res0.scen.horizon + 1)
        for c in res0.candidates:
            pd_, _ = plan.get(c.bill_id, (res0.scen.day(c.due_idx), 0))
            if pd_ is not None:
                plan_commit[max((pd_ - today).days, 0):] += c.amount
        tout = treasury.run(treasury.TreasuryIn(res0.scen, plan_commit, un0, rules.min_balance, rules.required_confidence,
                                                balance_on(session, today), balance_on(session, today, "reserve"), today))
        for p in session.execute(select(Proposal).where(Proposal.kind.in_(("sweep", "top_up")), Proposal.status == "open")).scalars():
            p.status = "superseded"
        for idea in tout.ideas:
            pid = f"p_{idea.kind}_{idea.on:%Y%m%d}"
            p = session.get(Proposal, pid)
            meta = {"reason": idea.reason, "reason_ms": idea.reason_ms, "interest_estimate": idea.interest_estimate,
                    "direction": "to_reserve" if idea.kind == "sweep" else "to_operating",
                    "covers_date": idea.covers_date.isoformat() if idea.covers_date else None}
            if p is None:
                session.add(Proposal(id=pid, kind=idea.kind, bill_id=None, payee="Reserve account (Demo bank)", account_ref=RESERVE_ACCOUNT,
                                     amount=idea.amount, proposed_date=idea.on, origin="treasury", status="open", meta=meta, created_at=now_iso()))
            elif p.status in ("superseded", "open"):
                p.status, p.amount, p.proposed_date, p.meta = "open", idea.amount, idea.on, meta
        session.flush()
        _record(session, run_id, "treasury", "ok", t, f"{len(tout.ideas)} suggestion(s): " + (", ".join(i.kind.replace('_', '-') for i in tout.ideas) or "nothing to move"))

    # Policy Engine ------------------------------------------------------------------------
    t = time.perf_counter()
    ctx, res, inp, decisions, stats = policy_pass(session, run_id, today, rules, plan)
    summary = _write_cash_range(session, run_id, today, rules, res, ctx)
    _record(session, run_id, "policy", "ok", t,
            f"{len(decisions)} proposals: {stats['ALLOW']} allow, {stats['HOLD']} hold, {stats['ESCALATE']} escalate, {stats['DENY']} deny"
            + (f"; {len(stats['flips'])} changed verdict" if stats["flips"] else ""), {k: v for k, v in stats.items()})

    # Human Review -----------------------------------------------------------------------------
    t = time.perf_counter()
    waiting = [d.proposal_id for d in decisions if d.verdict == "ESCALATE"]
    _record(session, run_id, "human", "ok" if waiting else "skipped", t,
            f"{len(waiting)} waiting for the owner" if waiting else "Nothing needs the owner", {"waiting": waiting})

    # Executor -------------------------------------------------------------------------------------
    t = time.perf_counter()
    receipts: list[Receipt] = []
    if execute:
        receipts = executor.execute_due(session, today)
    if receipts:
        ctx, res, inp, decisions, stats = policy_pass(session, run_id, today, rules, plan)  # settle against the new balance
        summary = _write_cash_range(session, run_id, today, rules, res, ctx)
    sent = [r for r in receipts if r.status == "accepted"]
    _record(session, run_id, "executor", "ok" if receipts else "skipped", t,
            f"Sent {len(sent)} payment(s) to the Demo bank" if receipts else ("Kill switch is on: nothing sent" if rules.kill_switch else "Nothing due to send"),
            {"receipts": [r.id for r in receipts]})

    # Explainer ----------------------------------------------------------------------------------------
    t = time.perf_counter()
    if mode == "full" or receipts:
        for r in receipts:
            p = session.get(Proposal, r.proposal_id)
            d_hist = [d.verdict for d in session.execute(select(Decision).where(Decision.proposal_id == p.id).order_by(Decision.id)).scalars()]
            last = executor.latest_decision(session, p.id)
            due = date.fromisoformat(p.meta["due"]) if p.meta.get("due") else today
            r.explanation = explainer.run_with_model(explainer.ExplainerIn(p.payee, p.amount, today, due, last.why if last else "", d_hist)).text
        _record(session, run_id, "explainer", "ok", t, f"Explained {len(receipts)} payment(s); CFO brief ready" if receipts else "CFO brief ready")
    else:
        _record(session, run_id, "explainer", "skipped", t, "Nothing new to explain")

    # Watchdog -----------------------------------------------------------------------------------------------
    t = time.perf_counter()
    report = watchdog.run(session, today, ctx, previous_range)
    _record(session, run_id, "watchdog", "ok", t,
            ("; ".join(a["message"] for a in report.alerts) if report.alerts else "Audit chain intact, attack self-test passed"),
            {"checks": report.checks})

    append(session, "pipeline", "pipeline.run", {
        "run_id": run_id, "mode": mode, "trigger": trigger, "sim_date": today.isoformat(),
        "verdicts": {k: stats[k] for k in ("ALLOW", "HOLD", "ESCALATE", "DENY")}, "paid": len(receipts),
        "p_ok_managed": summary["p_ok_managed"], "p_ok_unmanaged": summary["p_ok_unmanaged"],
    })
    session.flush()
    from helm import anchor as _anchor

    _anchor.auto_anchor(session)
    return run_id
