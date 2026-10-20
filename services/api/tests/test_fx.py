import httpx
import pytest

from helm import fx


def test_conversion_uses_the_quoted_rates():
    rates = {"rates": {"USD": 0.25, "SGD": 0.3}}
    assert fx.to_myr(100, "MYR", rates) == 100
    assert fx.to_myr(25, "USD", rates) == 100.0


def test_a_parsed_response_is_cached_and_an_outage_returns_none(monkeypatch):
    fx._cache.update(at=0.0, data=None)
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"amount": 1, "base": "MYR", "date": "2026-10-19", "rates": {"USD": 0.24}})))
    assert fx.fetch_rates(client=ok)["rates"]["USD"] == 0.24
    down = httpx.Client(transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("offline"))))
    assert fx.fetch_rates(client=down)["rates"]["USD"] == 0.24  # still the cached value
    fx._cache.update(at=0.0, data=None)
    assert fx.fetch_rates(client=down) is None


@pytest.mark.live
def test_live_frankfurter_answers_with_real_rates():
    """Hits the real service. Skipped automatically when the network is not reachable."""
    fx._cache.update(at=0.0, data=None)
    data = fx.fetch_rates()
    if data is None:
        pytest.skip("Frankfurter not reachable from here")
    assert data["base"] == "MYR" and {"USD", "SGD", "CNY"} <= set(data["rates"])
    assert 0 < data["rates"]["USD"] < 1
