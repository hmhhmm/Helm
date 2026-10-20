"""Seed determinism, the engineered story, and the three simulator flows end to end."""
from sqlalchemy import func, select

from helm import audit, executor, pipeline, simulator
from helm.db import SessionLocal, reset_db
from helm.models import Balance, Bill, Decision, Invoice, Receipt, Rules, Supplier
from helm.rules_view import sim_today
from helm.seed import build_world, seed_database
from helm.seed.world import TODAY


def test_seed_is_deterministic():
    a, b = build_world(), build_world()
    assert [(i.id, i.amount, i.pay_date) for i in a.invoices] == [(i.id, i.amount, i.pay_date) for i in b.invoices]
    assert [(x.id, x.amount, x.due) for x in a.bills] == [(x.id, x.amount, x.due) for x in b.bills]


def test_seed_matches_the_persona(session):
    assert session.scalar(select(func.count(Supplier.id)).where(Supplier.kind == "supplier")) == 12
    n_inv = session.scalar(select(func.count(Invoice.id)).where(Invoice.issued >= TODAY.replace(year=2025, month=10, day=20)))
    assert 125 <= n_inv <= 150
    assert session.get(Balance, (TODAY, "operating")).amount == 85_000
    rev = session.scalar(select(func.sum(Invoice.amount)).where(Invoice.issued >= TODAY.replace(year=2025, month=10, day=20), Invoice.issued <= TODAY))
    assert 1_000_000 < rev < 1_400_000
    assert session.get(Rules, 1).min_balance == 20_000


def test_reseeding_is_idempotent(fresh):
    def snap():
        with SessionLocal() as s:
            return (s.scalar(select(func.count(Invoice.id))), s.scalar(select(func.count(Bill.id))), s.scalar(select(func.sum(Bill.amount))))
    first = snap()
    from helm.bootstrap import reset_demo
    reset_demo()
    assert snap() == first


def test_the_crunch_is_real_and_helm_resolves_it(fresh, session):
    rng = pipeline_range(session)
    assert rng["p_ok_unmanaged"] < 0.9          # paying everything on time is risky
    assert rng["p_ok_managed"] >= 0.9           # Helm's plan restores the target
    assert rng["low_unmanaged"]["worst"] < 20_000
    holds = [d for d in pipeline.latest_decisions(session).values() if d.verdict == "HOLD"]
    assert holds and all(d.release_on and d.release_on > TODAY for d in holds)
    kertas = next(d for d in holds if "Syarikat Kertas" in d.why)
    assert "18,400" in kertas.why and "Releasing on" in kertas.why


def pipeline_range(session):
    from helm.views import latest_range
    return latest_range(session)


def test_customer_pays_late_flips_an_allow_to_hold_and_widens_the_band(fresh, session):
    r = simulator.customer_late(session)
    session.commit()
    assert r["applied"]
    assert r["band_width_after"] > r["band_width_before"]
    assert r["low_after"]["p50"] < r["low_before"]["p50"]
    assert any(f["from"] == "ALLOW" and f["to"] == "HOLD" for f in r["flips"])
    assert simulator.customer_late(session)["applied"] is False  # idempotent


def test_malicious_invoice_ends_in_escalate_with_no_money_moved(fresh, session):
    cash_before = session.get(Balance, (TODAY, "operating")).amount
    r = simulator.inject_malicious(session)
    session.commit()
    assert r["verdict"] == "ESCALATE" and r["quarantined"] and r["money_moved"] == 0
    assert session.get(Balance, (TODAY, "operating")).amount == cash_before
    from helm.models import AuditLog
    events = [(a.actor, a.event) for a in session.execute(select(AuditLog)).scalars()]
    assert ("reader", "doc.quarantined") in events
    assert ("policy", "decision.made") in events
    assert audit.verify_chain(session)["ok"]
    receipts = session.scalar(select(func.count(Receipt.id)))
    assert receipts == 0


def test_the_injected_instruction_is_never_followed(fresh, session):
    simulator.inject_malicious(session)
    d = executor.latest_decision(session, "p_bill_mal_1")
    assert d.verdict == "ESCALATE"
    assert session.execute(select(Receipt).where(Receipt.proposal_id == "p_bill_mal_1")).first() is None
    # the poison does not crowd out legitimate payments
    others = [x for pid, x in pipeline.latest_decisions(session).items() if pid != "p_bill_mal_1"]
    assert any(x.verdict == "ALLOW" for x in others)


def test_kill_switch_stops_the_executor_in_one_request(fresh, session):
    r = session.get(Rules, 1)
    r.kill_switch = True
    session.flush()
    pipeline.run_pipeline(session, mode="gate", trigger="test")
    # advance a week with the switch on: nothing may be sent
    session.get(Rules, 1).kill_switch = True
    out = simulator.advance_week(session)
    session.commit()
    assert out["paid"] == 0
    assert session.scalar(select(func.count(Receipt.id))) == 0
    assert all(d.verdict == "DENY" for d in pipeline.latest_decisions(session).values())


def test_advance_week_pays_what_was_allowed_and_keeps_the_chain_valid(fresh, session):
    out = simulator.advance_week(session)
    session.commit()
    assert sim_today(session) > TODAY
    assert out["paid"] > 0 and out["received"] > 0
    assert audit.verify_chain(session)["ok"]
    sent = session.execute(select(Receipt).where(Receipt.status == "accepted")).scalars().all()
    for r in sent:  # every payment traces back to an ALLOW decision
        ins = session.get(__import__("helm.models", fromlist=["Instruction"]).Instruction, r.instruction_id)
        assert session.get(Decision, ins.decision_id).verdict == "ALLOW"
    assert all(r.explanation for r in sent)


def test_a_payment_is_rechecked_on_the_day_it_would_go(fresh, session):
    """After the late-payment shock, advancing time must not release a bill the gate now holds."""
    simulator.customer_late(session)
    session.commit()
    held_ids = {pid for pid, d in pipeline.latest_decisions(session).items() if d.verdict == "HOLD"}
    simulator.advance_week(session)
    session.commit()
    paid = {r.proposal_id for r in session.execute(select(Receipt).where(Receipt.status == "accepted")).scalars()}
    for pid in paid & held_ids:
        d = executor.latest_decision(session, pid)
        assert d.verdict == "ALLOW"


def test_owner_approval_is_the_only_way_a_flagged_invoice_gets_paid(fresh, session):
    from tests.conftest import owner_client
    session.close()
    with owner_client() as c:
        m = c.post("/sim/malicious-invoice").json()["data"]
        pid = m["proposal_id"]
        assert c.get("/bank/ledger").json()["rows"] == []                   # nothing moved before the owner acts
        r = c.post(f"/decisions/{pid}/owner", json={"choice": "approve"}).json()
        assert r["verdict"] in ("ALLOW", "HOLD") and r["owner_choice"] == "approved"
        audit_events = [a["event"] for a in c.get("/audit?limit=200").json()["rows"]]
        assert "owner.approved" in audit_events
        assert c.post("/audit/verify").json()["ok"]


def test_holding_a_flagged_invoice_keeps_it_out_of_the_queue_for_good(fresh, session):
    from tests.conftest import owner_client
    session.close()
    with owner_client() as c:
        pid = c.post("/sim/malicious-invoice").json()["data"]["proposal_id"]
        assert c.post(f"/decisions/{pid}/owner", json={"choice": "hold"}).json()["status"] == "held_by_owner"
        c.post("/sim/advance-week")
        assert c.get("/bank/ledger").json()["rows"] == [] or all(r["to"] != "DEMO-9999-0042" for r in c.get("/bank/ledger").json()["rows"])
        assert pid not in [r["proposal_id"] for g in c.get("/payments").json()["groups"].values() for r in g if r["status"] == "queued"]


def test_four_weeks_run_without_trouble(fresh, session):
    for _ in range(4):
        simulator.advance_week(session)
        session.commit()
    assert audit.verify_chain(session)["ok"]
    assert session.get(Balance, (sim_today(session), "operating")).amount > 0
