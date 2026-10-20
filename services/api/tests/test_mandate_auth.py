"""The owner's mandate (daily cap, monthly cap, expiry) and owner login."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from helm import auth
from helm.engine.policy import evaluate_all
from helm.main import app
from tests.conftest import owner_client
from tests.test_policy_engine import TODAY, bill, check, ctx, rules, scen, verdict


# ---- mandate -------------------------------------------------------------------------------
def test_daily_cap_escalates_the_payment_that_would_cross_it():
    c = ctx(scen(level=200_000), rules(daily_cap=12_000))
    out = evaluate_all([bill(id="a", ref="A", amount=7_000), bill(id="b", ref="B", amount=7_000)], c)
    assert [d.verdict for d in out] == ["ALLOW", "ESCALATE"]
    assert check(out[1], "mandate")["result"] == "fail" and "daily cap" in out[1].why


def test_monthly_cap_counts_what_was_already_sent_this_month():
    c = ctx(scen(level=300_000), rules(monthly_cap=20_000))
    c.sent_by_day = {TODAY: 15_000.0}
    d = verdict(bill(amount=7_000, ref="M1"), c)
    assert d.verdict == "ESCALATE" and "monthly cap" in d.why
    assert check(d, "mandate")["month_total"] == 22_000


def test_a_payment_within_the_caps_is_still_allowed():
    c = ctx(scen(level=200_000), rules(daily_cap=50_000, monthly_cap=100_000))
    assert verdict(bill(amount=5_000, ref="OK1"), c).verdict == "ALLOW"


def test_caps_do_not_delay_statutory_or_payroll():
    c = ctx(scen(level=200_000), rules(daily_cap=1_000, monthly_cap=1_000))
    d = verdict(bill(payee="EPF (statutory)", account_ref="GOV-EPF", bill_kind="statutory", amount=40_000, ref="EPF-X"), c)
    assert d.verdict == "ALLOW"


def test_after_the_mandate_expires_everything_escalates_including_statutory():
    expired = TODAY - timedelta(days=1)
    c = ctx(scen(level=200_000), rules(mandate_expires=expired))
    assert verdict(bill(ref="E1"), c).verdict == "ESCALATE"
    stat = verdict(bill(payee="EPF (statutory)", account_ref="GOV-EPF", bill_kind="statutory", amount=4_000, ref="EPF-E"), ctx(scen(level=200_000), rules(mandate_expires=expired)))
    assert stat.verdict == "ESCALATE" and "mandate ended" in stat.why


def test_a_mandate_that_has_not_expired_changes_nothing():
    c = ctx(scen(level=200_000), rules(mandate_expires=TODAY + timedelta(days=30)))
    assert verdict(bill(ref="F1"), c).verdict == "ALLOW"


def test_owner_approval_clears_a_mandate_flag():
    c = ctx(scen(level=200_000), rules(daily_cap=1_000))
    assert verdict(bill(amount=5_000, ref="C1", owner_approved=True), c).verdict == "ALLOW"


def test_mandate_changes_are_validated_audited_and_enforced_through_the_api(fresh):
    with owner_client() as c:
        p = c.get("/policy").json()
        assert p["daily_cap"] == 60_000 and p["mandate_expires"] == "2027-06-30"
        body = {"min_balance": p["min_balance"], "risk_tolerance": p["risk_tolerance"], "approval_limit": p["approval_limit"],
                "protected_payees": p["protected_payees"], "daily_cap": 1_000, "monthly_cap": 5_000, "mandate_expires": "2027-06-30"}
        assert c.put("/policy", json={**body, "monthly_cap": 500}).status_code == 422   # monthly below daily
        assert c.put("/policy", json={**body, "daily_cap": -1}).status_code == 422
        assert c.put("/policy", json=body).status_code == 200
        pay = c.get("/payments").json()
        esc = [r for g in ("due_soon", "can_wait") for r in pay["groups"][g] if r["verdict"] == "ESCALATE"]
        assert esc, "a tiny daily cap must push optional payments to the owner"
        rows = c.get("/audit?limit=200").json()["rows"]
        changed = [r for r in rows if r["event"] == "rules.changed"][0]
        assert changed["payload"]["after"]["daily_cap"] == 1_000 and changed["payload"]["before"]["daily_cap"] == 60_000


# ---- owner login ------------------------------------------------------------------------------
PROTECTED = [
    ("POST", "/kill-switch", {"on": True}), ("POST", "/sim/advance-week", None), ("POST", "/sim/customer-late", None),
    ("POST", "/sim/malicious-invoice", None), ("POST", "/sim/reset", None), ("POST", "/sim/tamper", None),
    ("POST", "/anchor/run", None), ("POST", "/cash/p_x/execute", None), ("POST", "/decisions/p_x/owner", {"choice": "hold"}),
    ("POST", "/collections/c01/chase", None), ("PUT", "/collections/c01/tone", {"tone": "firm"}),
    ("PUT", "/policy", {"min_balance": 1, "risk_tolerance": 0.1, "approval_limit": 1, "protected_payees": []}),
]


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_unauthenticated_requests_to_state_changing_routes_are_refused(method, path, body):
    with TestClient(app) as c:
        r = c.request(method, path, json=body)
        assert r.status_code == 401, (path, r.text)
        bad = c.request(method, path, json=body, headers={"Authorization": "Bearer not-a-token"})
        assert bad.status_code == 401


def test_reading_screens_stays_open():
    with TestClient(app) as c:
        for path in ("/state", "/today", "/forecast", "/payments", "/policy", "/audit"):
            assert c.get(path).status_code == 200


def test_login_with_the_right_passcode_returns_a_token_that_works(fresh):
    with TestClient(app) as c:
        assert c.post("/auth/login", json={"passcode": "wrong"}).status_code == 401
        tok = c.post("/auth/login", json={"passcode": "helm-demo"}).json()["token"]
        assert c.post("/kill-switch", json={"on": False}, headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_tokens_expire_and_cannot_be_forged():
    t = auth.issue_token(now=1_000)["token"]
    assert auth.verify_token(t, now=1_000 + 60)
    assert not auth.verify_token(t, now=1_000 + auth.TOKEN_TTL_SECONDS + 1)
    body, sig = t.rsplit(".", 1)
    assert not auth.verify_token(body + "." + "0" * len(sig))
    assert not auth.verify_token(None) and not auth.verify_token("garbage")


def test_login_is_rate_limited():
    from fastapi import HTTPException
    for _ in range(5):
        assert auth.check_passcode("nope", client="rl-test", now=5_000) is False
    with pytest.raises(HTTPException) as e:
        auth.check_passcode("nope", client="rl-test", now=5_001)
    assert e.value.status_code == 429
