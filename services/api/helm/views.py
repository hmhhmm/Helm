"""Database -> screen-ready payloads. Plain dicts; helm.api.schemas gives them types for the web client."""
import json
import statistics
from datetime import date, timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from helm import audit as audit_mod
from helm import pipeline
from helm.config import DEMO_MODE, LLM_MODE, RESERVE_APY
from helm.fmt import fdate, pct, rm
from helm.forecast.backtest import track_record
from helm.forecast.montecarlo import forecast
from helm.forecast.service import balance_on, build_input
from helm.models import (
    AgentRun, AgentStep, Alert, AuditLog, Balance, Bill, BillPlan, CashRange, ChaseIdea, Customer, Decision,
    Document, Invoice, Proposal, Receipt, Rules, SimState, Supplier,
)
from helm.rules_view import RulesView, load_rules, sim_today


# ---------------------------------------------------------------------------- shared
def latest_range(session: Session) -> dict:
    row = session.execute(select(CashRange).order_by(CashRange.created_at.desc()).limit(1)).scalar_one()
    return row.summary


def _decisions_by_proposal(session: Session) -> dict[str, list[Decision]]:
    out: dict[str, list[Decision]] = {}
    for d in session.execute(select(Decision).order_by(Decision.id)).scalars():
        out.setdefault(d.proposal_id, []).append(d)
    return out


def _row(p: Proposal, hist: list[Decision], receipt: Receipt | None = None) -> dict:
    d = hist[-1] if hist else None
    prev = hist[-2] if len(hist) > 1 else None
    status = "sent" if p.status == "executed" else "held_by_owner" if p.status == "held_by_owner" else "queued"
    return {
        "proposal_id": p.id, "payee": p.payee, "amount": p.amount, "kind": p.kind, "bill_kind": p.meta.get("bill_kind"),
        "ref": p.meta.get("ref"), "label": p.meta.get("label"), "due": p.meta.get("due"),
        "release_on": d.release_on.isoformat() if d and d.release_on else None,
        "verdict": d.verdict if d else "HOLD", "why": d.why if d else "", "why_ms": (d.why_ms if d else "") or (d.why if d else ""),
        "previous_verdict": prev.verdict if prev else None,
        "previous_release_on": prev.release_on.isoformat() if prev and prev.release_on else None,
        "status": status, "quarantined": bool(p.meta.get("quarantined")), "p_ok": d.p_ok if d else None,
        "sent_on": receipt.sim_date.isoformat() if receipt else None, "doc_id": p.meta.get("doc_id"),
        "owner_choice": d.owner_choice if d else None,
    }


def state_view(session: Session) -> dict:
    today = sim_today(session)
    rules = session.get(Rules, 1)
    last = session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(1)).scalar_one_or_none()
    escalated = [
        p.id for p in session.execute(select(Proposal).where(Proposal.status == "open")).scalars()
        if (d := (_decisions_by_proposal_one(session, p.id))) and d.verdict == "ESCALATE"
    ]
    alerts = session.execute(select(Alert).where(Alert.resolved.is_(False)).order_by(Alert.id.desc())).scalars().all()
    return {
        "today": today.isoformat(), "synthetic": True, "kill_switch": rules.kill_switch, "min_balance": rules.min_balance,
        "operating": balance_on(session, today), "reserve": balance_on(session, today, "reserve"),
        "last_run_id": last.id if last else None, "demo_mode": DEMO_MODE, "llm_mode": LLM_MODE,
        "escalations": escalated,
        "alerts": [{"id": a.id, "level": a.level, "message": a.message, "ts": a.ts} for a in alerts],
    }


def _decisions_by_proposal_one(session: Session, pid: str) -> Decision | None:
    return session.execute(select(Decision).where(Decision.proposal_id == pid).order_by(Decision.id.desc()).limit(1)).scalar_one_or_none()


# ---------------------------------------------------------------------------- today
def _txt(en: str, ms: str) -> dict:
    return {"en": en, "ms": ms}


def today_view(session: Session) -> dict:
    today = sim_today(session)
    rules = load_rules(session)
    rng = latest_range(session)
    cash = balance_on(session, today)
    reserve = balance_on(session, today, "reserve")
    paid90 = session.scalar(select(func.sum(Bill.amount)).where(Bill.paid_on.is_not(None), Bill.paid_on > today - timedelta(days=90), Bill.paid_on <= today)) or 0.0
    burn = paid90 / 90 if paid90 else 1.0
    B = rules.min_balance
    hist = _decisions_by_proposal(session)
    props = {p.id: p for p in session.execute(select(Proposal)).scalars()}
    rows = [_row(props[pid], h) for pid, h in hist.items() if pid in props]
    holds = [r for r in rows if r["verdict"] == "HOLD" and r["status"] == "queued" and r["kind"] == "pay_bill"]
    escal = [r for r in rows if r["verdict"] == "ESCALATE" and r["status"] == "queued"]
    low = rng["low_unmanaged"]
    p_un, p_man, req = rng["p_ok_unmanaged"], rng["p_ok_managed"], rules.required_confidence
    risk = round((1 - p_un) * 100)
    low_date = date.fromisoformat(low["worst_date"])
    if p_un >= req:
        status = "ok"
        head = _txt(f"You're in good shape. Helm sees little risk of dropping under {rm(B)} in the next 90 days.",
                    f"Anda dalam keadaan baik. Helm nampak risiko kecil baki jatuh bawah {rm(B)} dalam 90 hari akan datang.")
    elif p_man >= req:
        status = "watch"
        head = _txt(f"You look fine today, but Helm sees a dip around {fdate(low_date)}: a {risk}% chance of falling under {rm(B)} if every bill is paid on its due date. "
                    f"Helm is holding {len(holds)} payment{'s' if len(holds) != 1 else ''} so you stay above it.",
                    f"Anda nampak baik hari ini, tetapi Helm nampak penurunan sekitar {fdate(low_date, 'ms')}: {risk}% risiko jatuh bawah {rm(B)} jika semua bil dibayar pada tarikh matang. "
                    f"Helm menahan {len(holds)} bayaran supaya anda kekal di atas.")
    else:
        status = "risk"
        head = _txt(f"Cash is tight: even with holds, there is a {round((1 - p_man) * 100)}% chance of dropping under {rm(B)}. Consider a top-up from the reserve.",
                    f"Tunai ketat: walaupun dengan penahanan, ada {round((1 - p_man) * 100)}% risiko jatuh bawah {rm(B)}. Pertimbangkan tambah baki daripada rizab.")
    needs: list[dict] = []
    for r in escal[:2]:
        needs.append({"kind": "approve", "title": _txt(f"Approve {r['payee']} {rm(r['amount'])}?", f"Lulus {r['payee']} {rm(r['amount'])}?"),
                      "detail": _txt(r["why"], r["why_ms"]), "href": f"/approve/{r['proposal_id']}", "proposal_id": r["proposal_id"]})
    for r in sorted(holds, key=lambda r: -r["amount"])[:1]:
        rel = date.fromisoformat(r["release_on"]) if r["release_on"] else None
        needs.append({"kind": "hold", "title": _txt(f"{r['payee']} {rm(r['amount'])} is on hold" + (f" until {fdate(rel)}" if rel else ""),
                                                    f"{r['payee']} {rm(r['amount'])} ditahan" + (f" hingga {fdate(rel, 'ms')}" if rel else "")),
                      "detail": _txt(r["why"], r["why_ms"]), "href": f"/payments?open={r['proposal_id']}", "proposal_id": r["proposal_id"]})
    idea = session.execute(select(ChaseIdea).order_by(ChaseIdea.rank).limit(1)).scalar_one_or_none()
    if idea and idea.effect_rm > 0:
        c = session.get(Customer, idea.customer_id)
        needs.append({"kind": "chase", "title": _txt(f"Chase {c.name}", f"Ingatkan {c.name}"),
                      "detail": _txt(idea.why, idea.why), "href": "/collections", "proposal_id": None})
    for a in session.execute(select(Alert).where(Alert.resolved.is_(False), Alert.level == "critical")).scalars():
        needs.insert(0, {"kind": "alert", "title": _txt("Watchdog alert", "Amaran Watchdog"), "detail": _txt(a.message, a.message), "href": "/agents", "proposal_id": None})
    top_up = session.execute(select(Proposal).where(Proposal.kind == "top_up", Proposal.status == "open")).scalars().first()
    if top_up and len(needs) < 3:
        needs.append({"kind": "top_up", "title": _txt(f"Move {rm(top_up.amount)} from the reserve?", f"Pindahkan {rm(top_up.amount)} daripada rizab?"),
                      "detail": _txt(top_up.meta.get("reason", ""), top_up.meta.get("reason_ms", "")), "href": "/cash", "proposal_id": top_up.id})
    week = [r for r in rows if r["kind"] == "pay_bill" and (
        (r["release_on"] and today - timedelta(days=3) <= date.fromisoformat(r["release_on"]) <= today + timedelta(days=7))
        or r["sent_on"] and date.fromisoformat(r["sent_on"]) >= today - timedelta(days=7))]
    week.sort(key=lambda r: (r["release_on"] or "9999", r["proposal_id"]))
    sent = {r.proposal_id: r for r in session.execute(select(Receipt)).scalars()}
    for w in week:
        if w["proposal_id"] in sent:
            w["sent_on"] = sent[w["proposal_id"]].sim_date.isoformat()
    return {
        "today": today.isoformat(), "cash_now": cash, "reserve": reserve, "min_balance": B,
        "buffer_days": round(max(0.0, (cash - B) / burn), 1), "runway_days": round(cash / burn, 1), "daily_burn": round(burn),
        "status": status, "headline": head,
        "low_point": {"date": low["date"], "p50": low["p50"], "worst_date": low["worst_date"], "worst": low["worst"], "chance_below_min": round(1 - p_un, 3)},
        "managed": {"p_ok": p_man, "required": req, "low_p10": rng["managed_low"]["p10"]},
        "needs_you": needs[:3], "week_decisions": week[:8], "kill_switch": rules.kill_switch,
    }


# ---------------------------------------------------------------------------- forecast
def _events(session: Session, today: date, rng: dict) -> list[dict]:
    props = {p.bill_id: p for p in session.execute(select(Proposal).where(Proposal.kind == "pay_bill")).scalars()}
    hist = _decisions_by_proposal(session)
    out = []
    for b in session.execute(select(Bill).where(Bill.paid_on.is_(None)).order_by(Bill.due)).scalars():
        if b.due > today + timedelta(days=90) or (b.kind == "supplier" and b.issued > today):
            continue
        p = props.get(b.id)
        d = hist.get(p.id, [None])[-1] if p else None
        out.append({"id": b.id, "date": max(b.due, today).isoformat(), "kind": b.kind if b.kind != "supplier" else "bill",
                    "label": b.payee, "amount": -b.amount, "verdict": d.verdict if d else None,
                    "release_on": d.release_on.isoformat() if d and d.release_on else None, "proposal_id": p.id if p else None})
    cust = {c.id: c.name for c in session.execute(select(Customer)).scalars()}
    for i in session.execute(select(Invoice).where(Invoice.paid_on.is_(None))).scalars():
        ex = rng["invoice_expect"].get(i.id)
        if ex and ex["median"]:
            out.append({"id": i.id, "date": ex["median"], "kind": "invoice", "label": cust.get(i.customer_id, ""), "amount": i.amount,
                        "verdict": None, "release_on": None, "proposal_id": None,
                        "range": [ex["p10"], ex["p90"]], "late_signal_days": i.late_signal_days, "customer_id": i.customer_id, "number": i.number})
    out.sort(key=lambda e: (e["date"], e["id"]))
    return out


def _causes(events: list[dict], rng: dict) -> dict:
    low = date.fromisoformat(rng["low_unmanaged"]["worst_date"])
    bills = [e for e in events if e["kind"] in ("bill",) and low - timedelta(days=21) <= date.fromisoformat(e["date"]) <= low]
    held = [e for e in bills if e["verdict"] == "HOLD"] or bills
    bill = max(held, key=lambda e: -e["amount"] * -1) if held else None
    bill = min(held, key=lambda e: e["amount"]) if held else None  # amounts are negative: min = largest outflow
    inv = [e for e in events if e["kind"] == "invoice" and low <= date.fromisoformat(e["date"]) <= low + timedelta(days=21)]
    invoice = max(inv, key=lambda e: e["amount"]) if inv else None
    return {"bill": bill, "invoice": invoice}


def forecast_payload(session: Session, rng: dict, rules: RulesView, *, events=None, extra: dict | None = None) -> dict:
    today = sim_today(session)
    events = events if events is not None else _events(session, today, rng)
    return {
        "today": today.isoformat(), "days": rng["days"], "unmanaged": rng["unmanaged"], "managed": rng["managed"],
        "min_balance": rng["min_balance"], "start": rng["start"], "required": rng["required_confidence"],
        "low": rng["low_unmanaged"], "managed_low": rng["managed_low"],
        "p_ok_unmanaged": rng["p_ok_unmanaged"], "p_ok_managed": rng["p_ok_managed"],
        "events": events, "causes": _causes(events, rng), "assumptions": rng["assumptions"],
        "track_record": track_record(session, today), **(extra or {}),
    }


def forecast_view(session: Session) -> dict:
    return forecast_payload(session, latest_range(session), load_rules(session))


def whatif_view(session: Session, late: list[dict], skip_bills: list[str]) -> dict:
    """Edit a projection without touching the ledger: re-forecast and re-run the gate, save nothing."""
    today = sim_today(session)
    rules = load_rules(session)
    extra_delay = {x["customer_id"]: int(x["days"]) for x in late if x.get("days")}
    inp = build_input(session, today, rules.horizon_days, extra_delay=extra_delay, skip_bills=set(skip_bills))
    res = forecast(inp)
    plan = {r.bill_id: (r.plan_date, r.days_late) for r in session.execute(select(BillPlan)).scalars()}
    ctx, decisions, ordered, prevs = pipeline.evaluate(session, today, rules, inp, res, plan, skip_bills=set(skip_bills))
    summary = pipeline.range_summary(rules, res, ctx)
    base = latest_range(session)
    by = {p.id: p for p in ordered}
    changes = []
    for d in decisions:
        p = by[d.proposal_id]
        prev = prevs.get(p.id)
        if p.kind != "pay_bill":
            continue
        if prev is None or prev.verdict != d.verdict or prev.release_on != d.release_on:
            changes.append({"proposal_id": p.id, "payee": p.payee, "amount": p.amount, "from": prev.verdict if prev else None,
                            "to": d.verdict, "release_from": prev.release_on.isoformat() if prev and prev.release_on else None,
                            "release_to": d.release_on.isoformat() if d.release_on else None, "why": d.why, "why_ms": d.why_ms})
    events = _events(session, today, summary)
    # carry the what-if verdicts onto the markers
    dec_by_bill = {by[d.proposal_id].bill_id: d for d in decisions if by[d.proposal_id].kind == "pay_bill"}
    for e in events:
        d = dec_by_bill.get(e["id"])
        if d:
            e["verdict"], e["release_on"] = d.verdict, d.release_on.isoformat() if d.release_on else None
    return forecast_payload(session, summary, rules, events=events, extra={
        "whatif": True, "changes": changes,
        "baseline": {"low": base["low_unmanaged"], "p_ok_unmanaged": base["p_ok_unmanaged"], "p_ok_managed": base["p_ok_managed"]},
    })


# ---------------------------------------------------------------------------- payments
def payments_view(session: Session) -> dict:
    today = sim_today(session)
    hist = _decisions_by_proposal(session)
    receipts = {r.proposal_id: r for r in session.execute(select(Receipt).where(Receipt.status == "accepted")).scalars()}
    groups = {"statutory": [], "due_soon": [], "can_wait": [], "paid": []}
    for p in session.execute(select(Proposal).where(Proposal.kind == "pay_bill").order_by(Proposal.proposed_date, Proposal.id)).scalars():
        h = hist.get(p.id, [])
        if not h:
            continue
        row = _row(p, h, receipts.get(p.id))
        if p.status == "executed":
            if row["sent_on"] and date.fromisoformat(row["sent_on"]) >= today - timedelta(days=21):
                groups["paid"].append(row)
            continue
        if p.status == "superseded":
            continue
        due = date.fromisoformat(p.meta["due"]) if p.meta.get("due") else p.proposed_date
        if row["bill_kind"] in ("statutory", "payroll"):
            groups["statutory"].append(row)
        elif due <= today + timedelta(days=14) or row["verdict"] in ("ESCALATE", "DENY"):
            groups["due_soon"].append(row)
        else:
            groups["can_wait"].append(row)
    groups["paid"].sort(key=lambda r: r["sent_on"] or "", reverse=True)
    queue = [r for g in ("statutory", "due_soon", "can_wait") for r in groups[g]]
    counts = {v: sum(1 for r in queue if r["verdict"] == v) for v in ("ALLOW", "HOLD", "ESCALATE", "DENY")}
    sentence = _txt(
        f"{counts['ALLOW']} released, {counts['HOLD']} waiting for cash, {counts['ESCALATE']} need you, {counts['DENY']} blocked.",
        f"{counts['ALLOW']} dilepaskan, {counts['HOLD']} menunggu tunai, {counts['ESCALATE']} perlukan anda, {counts['DENY']} disekat.",
    )
    return {"today": today.isoformat(), "groups": groups, "counts": counts, "summary": sentence}


def decision_view(session: Session, pid: str) -> dict | None:
    p = session.get(Proposal, pid)
    if p is None:
        return None
    hist = _decisions_by_proposal(session).get(pid, [])
    if not hist:
        return None
    d = hist[-1]
    receipt = session.execute(select(Receipt).where(Receipt.proposal_id == pid, Receipt.status == "accepted")).scalars().first()
    row = _row(p, hist, receipt)
    doc = session.get(Document, p.meta.get("doc_id")) if p.meta.get("doc_id") else None
    plan = session.execute(select(BillPlan).where(BillPlan.bill_id == p.bill_id).order_by(BillPlan.id.desc()).limit(1)).scalars().first() if p.bill_id else None
    bill = session.get(Bill, p.bill_id) if p.bill_id else None
    steps = [
        {"key": "read", "status": "done" if (doc or (bill and bill.source == "statutory_calendar")) else "na"},
        {"key": "planned", "status": "done" if plan else "na"},
        {"key": "policy", "status": "done"},
        {"key": "human", "status": ("current" if d.verdict == "ESCALATE" and p.status == "open" else
                                    "done" if d.owner_choice else "na")},
        {"key": "executor", "status": "done" if p.status == "executed" else "current" if d.verdict == "ALLOW" else "pending"},
        {"key": "bank", "status": "done" if receipt else "pending"},
    ]
    return {
        "row": row, "checks": d.checks, "consequence": d.consequence or {}, "timeline": steps,
        "history": [{"at": h.created_at, "verdict": h.verdict, "release_on": h.release_on.isoformat() if h.release_on else None, "why": h.why, "why_ms": h.why_ms} for h in hist],
        "document": ({"id": doc.id, "source": doc.source, "received_on": doc.received_on.isoformat(), "raw_text": doc.raw_text,
                      "extracted": doc.reader_json, "quarantined": doc.quarantined, "flags": doc.flags} if doc else None),
        "plan": ({"plan_date": plan.plan_date.isoformat() if plan.plan_date else None, "days_late": plan.days_late, "note": plan.note, "rank": plan.rank} if plan else None),
        "receipt": ({"id": receipt.id, "date": receipt.sim_date.isoformat(), "explanation": receipt.explanation, "bank": "Demo bank"} if receipt else None),
        "min_balance": session.get(Rules, 1).min_balance, "required": 1 - session.get(Rules, 1).risk_tolerance,
        "amount": p.amount,
    }


def try_view(session: Session, pid: str, on: date | None) -> dict | None:
    """Dry run: what would the gate say if this were paid on `on`? Saves nothing."""
    p = session.get(Proposal, pid)
    if p is None or p.kind != "pay_bill":
        return None
    today = sim_today(session)
    rules = load_rules(session)
    inp = build_input(session, today, rules.horizon_days)
    res = forecast(inp)
    plan = {r.bill_id: (r.plan_date, r.days_late) for r in session.execute(select(BillPlan)).scalars()}
    day = on or today
    ctx, decisions, ordered, prevs = pipeline.evaluate(session, today, rules, inp, res, plan, override_dates={pid: max(day, today)})
    d = next(x for x in decisions if x.proposal_id == pid)
    return {"proposal_id": pid, "on": max(day, today).isoformat(), "verdict": d.verdict, "why": d.why, "why_ms": d.why_ms,
            "release_on": d.release_on.isoformat() if d.release_on else None, "checks": d.checks, "payee": p.payee, "amount": p.amount}


# ---------------------------------------------------------------------------- collections
def dso_series(session: Session, today: date) -> list[dict]:
    """Days sales outstanding at each month end: open receivables / sales in the trailing 90 days x 90."""
    invs = session.execute(select(Invoice)).scalars().all()
    out = []
    m = date(today.year, today.month, 1)
    ends = []
    for k in range(12, 0, -1):
        y, mo = divmod(m.month - 1 - k, 12)
        first = date(m.year + y, mo + 1, 1)
        nxt = date(first.year + (first.month // 12), first.month % 12 + 1, 1)
        ends.append(nxt - timedelta(days=1))
    ends = [e for e in ends if e >= date(2026, 1, 1) or True]
    for e in ends:
        issued_by = [i for i in invs if i.issued <= e]
        open_ar = sum(i.amount for i in issued_by if not i.paid_on or i.paid_on > e)
        sales = sum(i.amount for i in invs if e - timedelta(days=90) < i.issued <= e)
        if sales > 0 and e >= date(2026, 1, 15):
            out.append({"month": e.strftime("%Y-%m"), "dso": round(open_ar / sales * 90, 1)})
    return out


def collections_view(session: Session) -> dict:
    today = sim_today(session)
    rng = latest_range(session)
    cust = {c.id: c for c in session.execute(select(Customer)).scalars()}
    buckets = {"not_due": [], "d1_30": [], "d31_60": [], "d60": []}
    for i in session.execute(select(Invoice).where(Invoice.paid_on.is_(None)).order_by(Invoice.due)).scalars():
        over = (today - i.due).days
        key = "not_due" if over <= 0 else "d1_30" if over <= 30 else "d31_60" if over <= 60 else "d60"
        ex = rng["invoice_expect"].get(i.id, {})
        buckets[key].append({
            "id": i.id, "number": i.number, "customer_id": i.customer_id, "customer": cust[i.customer_id].name, "amount": i.amount,
            "issued": i.issued.isoformat(), "due": i.due.isoformat(), "days_overdue": max(over, 0), "expected": ex.get("median"),
            "chased_on": i.chased_on.isoformat() if i.chased_on else None, "late_signal_days": i.late_signal_days, "doc_id": i.doc_id,
        })
    ideas = []
    for c in session.execute(select(ChaseIdea).order_by(ChaseIdea.rank)).scalars():
        cu = cust[c.customer_id]
        delays = [(i.paid_on - i.due).days for i in session.execute(select(Invoice).where(Invoice.customer_id == c.customer_id, Invoice.paid_on.is_not(None))).scalars()]
        ideas.append({"customer_id": c.customer_id, "customer": cu.name, "rank": c.rank, "effect_rm": c.effect_rm, "amount_open": c.amount_open,
                      "invoice_ids": c.invoice_ids, "tone": cu.tone, "why": c.why, "draft_en": c.draft_en, "draft_ms": c.draft_ms,
                      "avg_delay": round(statistics.mean(delays), 1) if delays else 0.0, "paid_count": len(delays)})
    series = dso_series(session, today)
    total_open = sum(x["amount"] for b in buckets.values() for x in b)
    return {
        "today": today.isoformat(), "ageing": buckets, "ideas": ideas, "dso": {"series": series, "current": series[-1]["dso"] if series else None},
        "total_open": total_open, "assumption_days": 10,
        "summary": _txt(f"{rm(total_open)} is waiting to be collected. Chase in this order to lift your low point the most.",
                        f"{rm(total_open)} menunggu dikutip. Ingatkan mengikut susunan ini untuk menaikkan titik terendah anda paling banyak."),
    }


# ---------------------------------------------------------------------------- cash
def cash_view(session: Session) -> dict:
    today = sim_today(session)
    rules = load_rules(session)
    op, res_bal = balance_on(session, today), balance_on(session, today, "reserve")
    hist = _decisions_by_proposal(session)
    ideas = []
    for p in session.execute(select(Proposal).where(Proposal.kind.in_(("sweep", "top_up")), Proposal.status == "open").order_by(Proposal.proposed_date)).scalars():
        h = hist.get(p.id, [])
        if not h:
            continue
        r = _row(p, h)
        r.update({"direction": p.meta.get("direction"), "reason": p.meta.get("reason"), "reason_ms": p.meta.get("reason_ms"),
                  "interest_estimate": p.meta.get("interest_estimate"), "on": p.proposed_date.isoformat()})
        ideas.append(r)
    rng = latest_range(session)
    return {
        "today": today.isoformat(), "operating": op, "reserve": res_bal, "min_balance": rules.min_balance, "comfort": rules.min_balance + 10_000,
        "ideas": ideas, "apy": RESERVE_APY, "apy_note": "Illustrative rate for an estimate only; not a quote from any bank.",
        "p_ok_unmanaged": rng["p_ok_unmanaged"], "p_ok_managed": rng["p_ok_managed"],
        "summary": _txt(
            "Nothing to move right now." if not ideas else f"Helm has {len(ideas)} suggestion{'s' if len(ideas) != 1 else ''} for your cash.",
            "Tiada apa perlu dipindahkan sekarang." if not ideas else f"Helm ada {len(ideas)} cadangan untuk tunai anda."),
    }


# ---------------------------------------------------------------------------- policy
def policy_view(session: Session) -> dict:
    today = sim_today(session)
    r = session.get(Rules, 1)
    hist = _decisions_by_proposal(session)
    props = {p.id: p for p in session.execute(select(Proposal)).scalars()}
    rows = [_row(props[pid], h) for pid, h in hist.items() if pid in props and props[pid].kind == "pay_bill" and props[pid].status == "open"]
    holds = sorted([x for x in rows if x["verdict"] == "HOLD"], key=lambda x: -x["amount"])
    req = round((1 - r.risk_tolerance) * 100)
    suppliers = [{"name": s.name, "kind": s.kind} for s in session.execute(select(Supplier).where(Supplier.kind == "supplier").order_by(Supplier.name)).scalars()]
    h0 = holds[0] if holds else None
    examples = {
        "min_balance": _txt(
            (f"Example: paying {h0['payee']} {rm(h0['amount'])} on its due date would risk dropping under {rm(r.min_balance)}, so Helm holds it until {fdate(date.fromisoformat(h0['release_on']))}." if h0 and h0["release_on"]
             else f"Example: if a bill would make it likely that you drop under {rm(r.min_balance)}, Helm holds it until it is safe."),
            (f"Contoh: membayar {h0['payee']} {rm(h0['amount'])} pada tarikh matang berisiko jatuh bawah {rm(r.min_balance)}, jadi Helm menahannya hingga {fdate(date.fromisoformat(h0['release_on']), 'ms')}." if h0 and h0["release_on"]
             else f"Contoh: jika sesuatu bil mungkin menjatuhkan baki bawah {rm(r.min_balance)}, Helm menahannya sehingga selamat.")),
        "risk": _txt(f"At {req}% sure, a payment goes out only if there is at least a {req}% chance you stay above the minimum afterwards. Higher means more holds; lower means fewer.",
                     f"Pada {req}% yakin, bayaran hanya dibuat jika ada sekurang-kurangnya {req}% peluang baki kekal di atas minimum. Lebih tinggi bermakna lebih banyak penahanan."),
        "approval": _txt(f"Example: an invoice for RM 48,000 from a supplier Helm has never paid would wait for your OK, because it is above {rm(r.approval_limit)}.",
                         f"Contoh: invois RM 48,000 daripada pembekal yang tidak pernah dibayar akan menunggu kelulusan anda, kerana melebihi {rm(r.approval_limit)}."),
        "protected": _txt("Example: if the bank account on a bill from a protected payee differs from the one on file, the payment is blocked, not just flagged. Helm also delays protected payees last.",
                          "Contoh: jika akaun bank pada bil penerima dilindungi berbeza daripada rekod, bayaran disekat. Helm juga menangguhkan penerima dilindungi paling akhir."),
        "statutory": _txt("EPF, SOCSO, EIS, PCB, SST and payroll are scheduled first and never delayed by the optimiser. (Context only, not a compliance claim.)",
                          "EPF, SOCSO, EIS, PCB, SST dan gaji dijadualkan dahulu dan tidak pernah ditangguhkan. (Konteks sahaja, bukan tuntutan pematuhan.)"),
    }
    return {
        "today": today.isoformat(), "min_balance": r.min_balance, "risk_tolerance": r.risk_tolerance,
        "required_confidence": round(1 - r.risk_tolerance, 4), "approval_limit": r.approval_limit,
        "protected_payees": r.protected_payees, "kill_switch": r.kill_switch, "suppliers": suppliers,
        "risk_options": [0.80, 0.85, 0.90, 0.95, 0.99], "examples": examples,
    }


# ---------------------------------------------------------------------------- agents & audit
ARCH = [
    {"id": "inputs", "label": "Inputs", "kind": "store", "reads": [], "writes": ["facts"], "note": "Bank feeds, invoices, ledger (synthetic)"},
    {"id": "reader", "n": 0, "label": "Reader Agent", "kind": "agent", "reads": ["bank feeds", "invoices", "ledger"], "writes": ["facts"], "note": "Reads documents. Writes clean facts. Has no tools."},
    {"id": "forecaster", "n": 1, "label": "Forecaster Agent", "kind": "agent", "reads": ["facts"], "writes": ["cash_range"], "note": "Predicts the next 90 days."},
    {"id": "collections", "n": 2, "label": "Collections Agent", "kind": "agent", "reads": ["facts"], "writes": ["chase_ideas"], "note": "Reads facts, incl. pay history. Plans chasers."},
    {"id": "scheduler", "n": 3, "label": "Scheduler Agent", "kind": "agent", "reads": ["cash_range"], "writes": ["bill_plan"], "note": "Reads cash range. Picks which bills to pay."},
    {"id": "treasury", "n": 4, "label": "Treasury Agent", "kind": "agent", "reads": ["bill_plan"], "writes": ["proposals"], "note": "Checks the plan. Plans sweeps and top-ups."},
    {"id": "policy", "label": "Policy Engine", "kind": "code", "reads": ["proposals", "rules"], "writes": ["decisions"], "note": "Checks every proposal against the owner's rules."},
    {"id": "human", "label": "Human Review", "kind": "human", "reads": ["decisions = ESCALATE"], "writes": ["owner's choice"], "note": "The owner approves or holds."},
    {"id": "executor", "label": "Executor", "kind": "code", "reads": ["decisions = ALLOW"], "writes": ["instructions", "receipts"], "note": "Sends approved payments, expiring keys."},
    {"id": "explainer", "n": 5, "label": "Explainer Agent", "kind": "agent", "reads": ["receipts", "audit_log"], "writes": ["CFO brief"], "note": "Reads receipts. Writes why paid, why held."},
    {"id": "watchdog", "label": "Watchdog", "kind": "code", "reads": ["audit_log"], "writes": ["alerts", "kill switch"], "note": "Reads the log. Checks drift, tests attacks."},
]


def agents_view(session: Session) -> dict:
    last = session.execute(select(AgentRun).order_by(AgentRun.id.desc()).limit(1)).scalar_one_or_none()
    full = session.execute(select(AgentRun).where(AgentRun.mode == "full").order_by(AgentRun.id.desc()).limit(1)).scalar_one_or_none()
    steps = {}
    for node in [a["id"] for a in ARCH]:
        for run in (last, full):
            if run is None:
                continue
            s = session.execute(select(AgentStep).where(AgentStep.run_id == run.id, AgentStep.node == node)).scalars().first()
            if s and (s.status != "skipped" or node not in steps):
                steps[node] = {"status": s.status, "ms": s.ms, "summary": s.summary, "run_id": run.id}
                if s.status != "skipped":
                    break
    log = []
    for s, r in session.execute(select(AgentStep, AgentRun).join(AgentRun, AgentRun.id == AgentStep.run_id).order_by(AgentStep.id.desc()).limit(60)).all():
        log.append({"id": s.id, "run_id": r.id, "sim_date": r.sim_date.isoformat(), "mode": r.mode, "trigger": r.trigger, "node": s.node,
                    "status": s.status, "ms": s.ms, "summary": s.summary})
    alerts = [{"id": a.id, "level": a.level, "message": a.message, "ts": a.ts, "resolved": a.resolved}
              for a in session.execute(select(Alert).order_by(Alert.id.desc()).limit(20)).scalars()]
    return {
        "nodes": [{**a, "step": steps.get(a["id"])} for a in ARCH], "log": log, "alerts": alerts,
        "kill_switch": session.get(Rules, 1).kill_switch, "llm_mode": LLM_MODE,
        "last_run": {"id": last.id, "ts": last.ts, "mode": last.mode, "trigger": last.trigger, "sim_date": last.sim_date.isoformat()} if last else None,
        "audit_rows": session.scalar(select(func.count(AuditLog.id))) or 0,
    }


def audit_page(session: Session, before: int | None, limit: int = 40) -> dict:
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if before:
        q = q.where(AuditLog.id < before)
    rows = session.execute(q).scalars().all()
    return {"rows": [{"id": r.id, "ts": r.ts, "actor": r.actor, "event": r.event, "payload": r.payload, "prev_hash": r.prev_hash, "hash": r.hash} for r in rows],
            "total": session.scalar(select(func.count(AuditLog.id))) or 0}


def document_view(session: Session, doc_id: str) -> dict | None:
    d = session.get(Document, doc_id)
    if d is None:
        return None
    return {"id": d.id, "kind": d.kind, "source": d.source, "received_on": d.received_on.isoformat(), "raw_text": d.raw_text,
            "extracted": d.reader_json, "quarantined": d.quarantined, "flags": d.flags, "linked_id": d.linked_id}
