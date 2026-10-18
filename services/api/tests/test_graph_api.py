from fastapi.testclient import TestClient

from helm import graph
from helm.main import app


def test_graph_matches_the_architecture():
    assert graph.replay(escalated=False) == ["reader", "forecaster", "collections", "scheduler", "treasury", "policy", "executor", "explainer", "watchdog"]
    assert graph.replay(escalated=True) == ["reader", "forecaster", "collections", "scheduler", "treasury", "policy", "human", "executor", "explainer", "watchdog"]
    assert "policy" in graph.mermaid()


def test_api_contract_smoke(fresh):
    with TestClient(app) as c:
        for path in ["/state", "/today", "/forecast", "/payments", "/collections", "/cash", "/policy", "/agents", "/agents/graph", "/audit", "/bank/ledger"]:
            r = c.get(path)
            assert r.status_code == 200, path
        assert c.get("/brief.pdf").content[:4] == b"%PDF"
        assert c.get("/state").json()["synthetic"] is True
        assert c.post("/audit/verify").json()["ok"] is True
        assert c.get("/decisions/nope").status_code == 404
        # policy validation
        bad = {"min_balance": -5, "risk_tolerance": 0.1, "approval_limit": 1000, "protected_payees": []}
        assert c.put("/policy", json=bad).status_code == 422
        # owner actions are refused when nothing is waiting
        pid = c.get("/payments").json()["groups"]["can_wait"][0]["proposal_id"]
        assert c.post(f"/decisions/{pid}/owner", json={"choice": "approve"}).status_code == 409


def test_policy_change_is_audited_and_changes_decisions(fresh):
    with TestClient(app) as c:
        p = c.get("/policy").json()
        body = {"min_balance": p["min_balance"], "risk_tolerance": 0.01, "approval_limit": p["approval_limit"], "protected_payees": p["protected_payees"]}
        prev = c.post("/policy/preview", json=body).json()
        assert prev["counts"]["HOLD"] >= prev["baseline"]["HOLD"]  # stricter means more holds, never fewer
        assert c.put("/policy", json=body).status_code == 200
        events = [r["event"] for r in c.get("/audit?limit=200").json()["rows"]]
        assert "rules.changed" in events
        assert c.get("/policy").json()["required_confidence"] == 0.99
