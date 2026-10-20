"""Wise adapter tests run on a mocked transport. No test calls the real sandbox."""
import httpx
import pytest

from helm import config
from helm.bank import service as bank
from helm.bank import wise


def _transport(calls):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p = req.url.path
        if p == "/v2/profiles":
            return httpx.Response(200, json=[{"id": 7}])
        if p.endswith("/quotes"):
            return httpx.Response(200, json={"id": "q-1"})
        if p == "/v1/accounts":
            return httpx.Response(200, json={"id": 55})
        if p == "/v1/transfers":
            return httpx.Response(200, json={"id": 900, "status": "incoming_payment_waiting"})
        if "/simulation/" in p:
            return httpx.Response(200, json={"status": p.rsplit("/", 1)[1]})
        return httpx.Response(200, json={"id": 900, "status": "outgoing_payment_sent", "sourceValue": 330.0, "sourceCurrency": "GBP",
                                         "targetValue": 1850.0, "targetCurrency": "MYR", "rate": 5.6, "reference": "KCP-1"})
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _wise_env(monkeypatch):
    monkeypatch.setattr(config, "WISE_API_KEY", "test-key")
    monkeypatch.setattr(config, "WISE_PROFILE_ID", 0)
    wise._recipients.clear()
    wise._profile.clear()
    wise.CALL_LOG.clear()


def test_pay_runs_quote_recipient_transfer_and_simulation():
    calls = []
    out = wise.pay("Kimia Cuci", "MY-001", 1850.0, "KCP-1", client=httpx.Client(transport=_transport(calls)))
    assert out["status"] == "outgoing_payment_sent" and out["transfer_id"] == 900 and out["target_amount"] == 1850.0
    assert [m for m, _ in calls][:4] == ["GET", "POST", "POST", "POST"]
    assert sum("/simulation/" in p for _, p in calls) == 3


def test_call_log_never_holds_the_key():
    wise.pay("A", "1", 10.0, "r", client=httpx.Client(transport=_transport([])))
    assert "test-key" not in str(wise.CALL_LOG) and wise.CALL_LOG


def test_http_error_becomes_wise_error():
    t = httpx.MockTransport(lambda r: httpx.Response(403, json={"error": "forbidden"}))
    with pytest.raises(wise.WiseError):
        wise.pay("A", "1", 10.0, "r", client=httpx.Client(transport=t))


def test_test_account_number_is_stable_and_valid():
    a = wise._test_account_number("MY-ACC-0042")
    assert a == wise._test_account_number("MY-ACC-0042") and a.isdigit() and len(a) == 12


def test_bank_checks_key_before_calling_wise(session, monkeypatch):
    monkeypatch.setattr(config, "BANK_PROVIDER", "wise")
    called = []
    monkeypatch.setattr(wise, "pay", lambda *a, **k: called.append(1) or {})
    r = bank.submit(session, key="forged", instruction_id="i1", from_account="A", to_account="B", amount=5.0, scope="x", external=True)
    assert r["status"] == "rejected" and not called
