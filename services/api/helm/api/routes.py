from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm import audit, brief, executor, pipeline, simulator, views
from helm.auth import check_passcode, issue_token, require_owner
from helm.api import schemas as S
from helm.audit import append
from helm.db import get_session
from helm.fmt import rm
from helm.forecast.montecarlo import forecast
from helm.forecast.service import build_input
from helm.models import Customer, Decision, Document, Invoice, Proposal, Rules, SimTruth
from helm.rules_view import RulesView, load_rules, sim_today

router = APIRouter()


def _commit(session: Session, payload):
    session.commit()
    return payload


# ---- state --------------------------------------------------------------------
@router.get("/state", response_model=S.StateOut, tags=["state"])
def state(session: Session = Depends(get_session)):
    out = views.state_view(session)
    chain = audit.verify_chain(session)
    return {**out, "chain_ok": chain["ok"], "chain_broken_at": chain["broken_at"]}


@router.get("/today", response_model=S.TodayOut, tags=["screens"])
def today(session: Session = Depends(get_session)):
    return views.today_view(session)


@router.get("/forecast", response_model=S.ForecastOut, tags=["screens"])
def forecast_get(session: Session = Depends(get_session)):
    return views.forecast_view(session)


@router.post("/forecast/whatif", response_model=S.ForecastOut, tags=["screens"])
def forecast_whatif(body: S.WhatIfIn, session: Session = Depends(get_session)):
    return views.whatif_view(session, [x.model_dump() for x in body.late], body.skip_bill_ids)


@router.get("/payments", response_model=S.PaymentsOut, tags=["screens"])
def payments(session: Session = Depends(get_session)):
    return views.payments_view(session)


@router.get("/decisions/{proposal_id}", response_model=S.DecisionOut, tags=["decisions"])
def decision(proposal_id: str, session: Session = Depends(get_session)):
    d = views.decision_view(session, proposal_id)
    if d is None:
        raise HTTPException(404, "No decision for that proposal")
    return d


@router.get("/decisions/{proposal_id}/try", response_model=S.TryOut, tags=["decisions"])
def decision_try(proposal_id: str, on: date | None = None, session: Session = Depends(get_session)):
    d = views.try_view(session, proposal_id, on)
    if d is None:
        raise HTTPException(404, "Not a payable proposal")
    return d


@router.post("/decisions/{proposal_id}/owner", dependencies=[Depends(require_owner)], response_model=S.Row, tags=["decisions"])
def owner_choice(proposal_id: str, body: S.OwnerIn, session: Session = Depends(get_session)):
    p = session.get(Proposal, proposal_id)
    d = executor.latest_decision(session, proposal_id)
    if p is None or d is None:
        raise HTTPException(404, "Unknown proposal")
    if p.status != "open" or d.verdict != "ESCALATE":
        raise HTTPException(409, "This payment is not waiting for you")
    if body.choice == "approve":
        d.owner_choice = "approved"
        append(session, "human", "owner.approved", {"proposal_id": p.id, "payee": p.payee, "amount": p.amount})
        pipeline.run_pipeline(session, mode="gate", trigger=f"owner approved {p.id}")
    else:
        d.owner_choice = "hold"
        p.status = "held_by_owner"
        append(session, "human", "owner.held", {"proposal_id": p.id, "payee": p.payee, "amount": p.amount, "money_moved": 0})
    session.commit()
    hist = views._decisions_by_proposal(session).get(p.id, [])
    return views._row(p, hist)


@router.post("/payments/new", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["decisions"])
def new_payment(body: S.NewPaymentIn, session: Session = Depends(get_session)):
    """The owner enters a payment. A payee Helm has not paid before waits for the owner's approval."""
    from helm import live

    pid = live.enter_payment(session, body.payee, body.amount, body.reference)
    session.commit()
    return S.SimOut(message=f"Payment to {body.payee.strip()} is ready for your decision.", data={"proposal_id": pid})


# ---- collections -------------------------------------------------------------------
@router.get("/collections", response_model=S.CollectionsOut, tags=["screens"])
def collections(session: Session = Depends(get_session)):
    return views.collections_view(session)


@router.get("/invoices/{invoice_id}/einvoice", tags=["collections"])
def einvoice(invoice_id: str, session: Session = Depends(get_session)):
    """The MyInvois e-invoice document for one invoice. It is generated, not submitted."""
    from helm import einvoice as ei

    inv = session.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "invoice not found")
    return {"invoice_id": inv.id, "number": inv.number, "status": ei.status(inv), "submitted": False, "document": ei.build(inv, session.get(Customer, inv.customer_id))}


@router.put("/collections/{customer_id}/tone", tags=["collections"], dependencies=[Depends(require_owner)])
def set_tone(customer_id: str, body: S.ToneIn, session: Session = Depends(get_session)):
    c = session.get(Customer, customer_id)
    if c is None:
        raise HTTPException(404, "Unknown customer")
    c.tone = body.tone
    append(session, "owner", "collections.tone_changed", {"customer": c.name, "tone": body.tone})
    # redraft with the new tone
    from helm.agents import collections as ca
    from helm.models import ChaseIdea
    idea = session.execute(select(ChaseIdea).where(ChaseIdea.customer_id == customer_id)).scalars().first()
    if idea:
        today = sim_today(session)
        invs = session.execute(select(Invoice).where(Invoice.customer_id == customer_id, Invoice.paid_on.is_(None))).scalars().all()
        view = ca.CustomerView(c.id, c.name, body.tone, 0, [ca.OpenInvoice(i.id, i.number, i.amount, i.due, None) for i in invs])
        idea.draft_en, idea.draft_ms = ca.draft(view, today)
        idea.tone = body.tone
    session.commit()
    return {"ok": True}


@router.post("/collections/{customer_id}/chase", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["collections"])
def chase(customer_id: str, session: Session = Depends(get_session)):
    c = session.get(Customer, customer_id)
    if c is None:
        raise HTTPException(404, "Unknown customer")
    today = sim_today(session)
    invs = session.execute(select(Invoice).where(Invoice.customer_id == customer_id, Invoice.paid_on.is_(None))).scalars().all()
    for i in invs:
        i.chased_on = today
        t = session.get(SimTruth, i.id)
        if t:  # simulated world: a reminder pulls payment forward by up to 5 days
            t.pay_date = max(today + __import__("datetime").timedelta(days=1), t.pay_date - __import__("datetime").timedelta(days=5))
    append(session, "owner", "chase.sent", {"customer": c.name, "invoices": [i.number for i in invs], "note": "Marked as chased. Helm sent no message."})
    session.commit()
    return {"ok": True, "message": f"Marked {len(invs)} invoice(s) for {c.name} as chased. Helm sent no message.", "data": {}}


# ---- cash ---------------------------------------------------------------------------
@router.get("/cash", response_model=S.CashOut, tags=["screens"])
def cash(session: Session = Depends(get_session)):
    return views.cash_view(session)


@router.post("/cash/{proposal_id}/execute", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["cash"])
def cash_execute(proposal_id: str, session: Session = Depends(get_session)):
    p = session.get(Proposal, proposal_id)
    d = executor.latest_decision(session, proposal_id)
    if p is None or p.kind not in ("sweep", "top_up") or d is None:
        raise HTTPException(404, "Not a cash suggestion")
    if p.status != "open" or d.verdict != "ALLOW":
        raise HTTPException(409, "Helm cannot do this right now")
    r = executor.execute_one(session, p, d, sim_today(session))
    if r is None:
        session.commit()
        raise HTTPException(409, "The Executor refused (kill switch is on)")
    pipeline.run_pipeline(session, mode="full", trigger=f"owner moved cash {p.id}", execute=False)
    session.commit()
    return {"ok": r.status == "accepted", "message": f"Moved {rm(p.amount)} ({'reserve to operating' if p.kind == 'top_up' else 'operating to reserve'}).", "data": {"receipt": r.id}}


# ---- policy --------------------------------------------------------------------------
@router.get("/policy", response_model=S.PolicyOut, tags=["screens"])
def policy(session: Session = Depends(get_session)):
    return views.policy_view(session)


def _validate(body: S.PolicyIn) -> None:
    if not (0 <= body.min_balance <= 1_000_000):
        raise HTTPException(422, "Minimum balance must be between RM 0 and RM 1,000,000")
    if not (0.001 <= body.risk_tolerance <= 0.5):
        raise HTTPException(422, "Risk tolerance must be between 0.1% and 50%")
    if not (0 < body.approval_limit <= 10_000_000):
        raise HTTPException(422, "Approval limit must be above RM 0")
    for name, v in (("daily cap", body.daily_cap), ("monthly cap", body.monthly_cap)):
        if v is not None and not (0 < v <= 100_000_000):
            raise HTTPException(422, f"The {name} must be above RM 0, or left empty for no cap")
    if body.daily_cap is not None and body.monthly_cap is not None and body.monthly_cap < body.daily_cap:
        raise HTTPException(422, "The monthly cap cannot be below the daily cap")


@router.put("/policy", response_model=S.PolicyOut, tags=["screens"], dependencies=[Depends(require_owner)])
def policy_put(body: S.PolicyIn, session: Session = Depends(get_session)):
    _validate(body)
    r = session.get(Rules, 1)
    before = {"min_balance": r.min_balance, "risk_tolerance": r.risk_tolerance, "approval_limit": r.approval_limit, "protected_payees": list(r.protected_payees),
              "daily_cap": r.daily_cap, "monthly_cap": r.monthly_cap, "mandate_expires": r.mandate_expires.isoformat() if r.mandate_expires else None}
    r.min_balance, r.risk_tolerance, r.approval_limit = body.min_balance, body.risk_tolerance, body.approval_limit
    r.protected_payees = body.protected_payees
    r.daily_cap, r.monthly_cap, r.mandate_expires = body.daily_cap, body.monthly_cap, body.mandate_expires
    append(session, "owner", "rules.changed", {"before": before, "after": body.model_dump()})
    pipeline.run_pipeline(session, mode="full", trigger="rules changed")
    session.commit()
    return views.policy_view(session)


@router.post("/policy/preview", response_model=S.PolicyPreview, tags=["screens"])
def policy_preview(body: S.PolicyIn, session: Session = Depends(get_session)):
    """What would change if the owner saved these rules? Nothing is saved."""
    _validate(body)
    today = sim_today(session)
    cur = load_rules(session)
    new = RulesView(body.min_balance, body.risk_tolerance, body.approval_limit, tuple(body.protected_payees), cur.kill_switch, cur.horizon_days,
                    body.daily_cap, body.monthly_cap, body.mandate_expires)
    inp = build_input(session, today, cur.horizon_days)
    res = forecast(inp)
    from helm.models import BillPlan
    plan = {x.bill_id: (x.plan_date, x.days_late) for x in session.execute(select(BillPlan)).scalars()}
    _, base_dec, _, _ = pipeline.evaluate(session, today, cur, inp, res, plan)
    ctx, dec, ordered, prevs = pipeline.evaluate(session, today, new, inp, res, plan)
    by = {p.id: p for p in ordered}
    base = {d.proposal_id: d for d in base_dec}
    def count(ds):
        c = {"ALLOW": 0, "HOLD": 0, "ESCALATE": 0, "DENY": 0}
        for d in ds:
            if by[d.proposal_id].kind == "pay_bill":
                c[d.verdict] += 1
        return c
    changes = []
    for d in dec:
        b = base[d.proposal_id]
        if by[d.proposal_id].kind == "pay_bill" and (b.verdict != d.verdict or b.release_on != d.release_on):
            changes.append({"payee": by[d.proposal_id].payee, "amount": by[d.proposal_id].amount, "from": b.verdict, "to": d.verdict,
                            "release_from": b.release_on.isoformat() if b.release_on else None, "release_to": d.release_on.isoformat() if d.release_on else None})
    return {"counts": count(dec), "baseline": count(base_dec), "changes": changes}


@router.post("/kill-switch", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["safety"])
def kill_switch(body: S.KillIn, session: Session = Depends(get_session)):
    r = session.get(Rules, 1)
    r.kill_switch = body.on
    append(session, "owner", "kill_switch.engaged" if body.on else "kill_switch.released", {"by": "owner"})
    session.flush()
    pipeline.run_pipeline(session, mode="gate", trigger="kill switch " + ("on" if body.on else "off"))
    session.commit()
    return {"ok": True, "message": "Kill switch is ON: the Executor refuses everything." if body.on else "Kill switch released.", "data": {"kill_switch": body.on}}


# ---- agents & audit -------------------------------------------------------------------
@router.get("/agents", response_model=S.AgentsOut, tags=["screens"])
def agents(session: Session = Depends(get_session)):
    return views.agents_view(session)


@router.get("/agents/graph", tags=["screens"])
def agents_graph(session: Session = Depends(get_session)):
    from helm import graph
    from sqlalchemy import select as _sel
    from helm.models import AgentRun, AgentStep
    last = session.execute(_sel(AgentRun).order_by(AgentRun.id.desc()).limit(1)).scalar_one_or_none()
    escalated = False
    if last:
        h = session.execute(_sel(AgentStep).where(AgentStep.run_id == last.id, AgentStep.node == "human")).scalars().first()
        escalated = bool(h and h.status == "ok")
    return {"engine": "langgraph", "mermaid": graph.mermaid(), "path": graph.replay(escalated), "run_id": last.id if last else None}


@router.get("/audit", response_model=S.AuditPage, tags=["audit"])
def audit_rows(before: int | None = None, limit: int = Query(40, le=200), session: Session = Depends(get_session)):
    return views.audit_page(session, before, limit)


@router.post("/audit/verify", response_model=S.VerifyOut, tags=["audit"])
def audit_verify(session: Session = Depends(get_session)):
    return audit.verify_chain(session)


@router.get("/documents/{doc_id}", tags=["documents"])
def document(doc_id: str, session: Session = Depends(get_session)):
    d = views.document_view(session, doc_id)
    if d is None:
        raise HTTPException(404, "No such document")
    return d


@router.get("/brief.pdf", tags=["brief"])
def brief_pdf(session: Session = Depends(get_session)):
    return Response(brief.build_pdf(session), media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="helm-cfo-brief.pdf"'})


# ---- simulator ----------------------------------------------------------------------------
@router.post("/sim/advance-week", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["simulator"])
def sim_advance(session: Session = Depends(get_session)):
    r = simulator.advance_week(session)
    session.commit()
    return {"ok": True, "message": r["message"], "data": r}


@router.post("/sim/customer-late", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["simulator"])
def sim_late(session: Session = Depends(get_session)):
    r = simulator.customer_late(session)
    session.commit()
    return {"ok": r.get("applied", False), "message": r["message"], "data": r}


@router.post("/sim/malicious-invoice", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["simulator"])
def sim_malicious(session: Session = Depends(get_session)):
    r = simulator.inject_malicious(session)
    session.commit()
    return {"ok": r.get("injected", False), "message": r["message"], "data": r}


@router.post("/sim/reset", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["simulator"])
def sim_reset():
    from helm.bootstrap import reset_demo
    reset_demo()
    return {"ok": True, "message": "Reset to the seeded start (19 Oct 2026).", "data": {}}


@router.post("/sim/tamper", dependencies=[Depends(require_owner)], response_model=S.SimOut, tags=["simulator"])
def sim_tamper(session: Session = Depends(get_session)):
    """Edit one audit row the way someone with database admin rights could."""
    session.commit()
    r = audit.tamper_for_demo()
    return {"ok": True, "message": f"Audit row {r['tampered']} was edited directly in the database. Press Verify chain.", "data": r}


# --- owner login ----------------------------------------------------------------------------
@router.get("/auth/config", tags=["auth"])
def auth_config():
    """Tells the web app whether to show the demo passcode hint (only while the default passcode is in use)."""
    from helm import config
    return {"demo_hint": config.OWNER_PASSCODE if config.OWNER_PASSCODE == "helm-demo" else None}


@router.post("/auth/login", tags=["auth"])
def auth_login(body: dict, request: Request):
    who = request.client.host if request.client else "local"
    if not check_passcode(str(body.get("passcode", "")), who):
        raise HTTPException(401, "Wrong passcode")
    return issue_token()


# --- on-chain anchor (hashes only) -------------------------------------------------------
@router.get("/anchor", tags=["anchor"])
def anchor_status(session: Session = Depends(get_session)):
    from sqlalchemy import select as _s
    from helm import config
    from helm.models import Anchor
    rows = session.execute(_s(Anchor).order_by(Anchor.id.desc()).limit(20)).scalars().all()
    return {
        "enabled": bool(config.ANCHOR_RPC_URL and config.ANCHOR_PRIVATE_KEY and config.ANCHOR_CONTRACT),
        "contract": config.ANCHOR_CONTRACT or None,
        "explorer_tx": config.ANCHOR_EXPLORER_TX,
        "anchors": [{"kind": a.kind, "seq": a.seq, "hash": a.hash, "tx_hash": a.tx_hash, "block": a.block_number,
                     "chain_id": a.chain_id, "status": a.status, "at": a.created_at} for a in rows],
    }


@router.post("/anchor/run", tags=["anchor"], dependencies=[Depends(require_owner)])
def anchor_run(session: Session = Depends(get_session)):
    from helm import anchor as _a
    chain = _a.ChainClient.from_env()
    if chain is None:
        raise HTTPException(409, "On-chain anchoring is not configured. Set ANCHOR_RPC_URL, ANCHOR_PRIVATE_KEY and ANCHOR_CONTRACT.")
    rows = _a.anchor_now(session, chain)
    session.commit()
    return {"anchored": [{"kind": r.kind, "seq": r.seq, "hash": r.hash, "tx_hash": r.tx_hash, "status": r.status} for r in rows]}


@router.post("/anchor/verify", tags=["anchor"])
def anchor_verify(session: Session = Depends(get_session)):
    from helm import anchor as _a
    chain = _a.ChainClient.from_env()
    if chain is None:
        raise HTTPException(409, "On-chain anchoring is not configured.")
    return _a.verify_anchors(session, chain)


# --- live FX (Frankfurter) -----------------------------------------------------------------
@router.get("/fx", tags=["fx"])
def fx():
    from helm import fx as _fx
    data = _fx.fetch_rates()
    return data or {"source": "frankfurter.dev", "available": False}
