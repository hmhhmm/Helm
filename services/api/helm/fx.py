"""Live MYR exchange rates from Frankfurter (free, no key). Used for bills in other currencies.
If the service is unreachable the app carries on without rates and says so."""
import time

import httpx

URL = "https://api.frankfurter.dev/v1/latest"
_cache: dict = {"at": 0.0, "data": None}
TTL = 3600


def fetch_rates(symbols: str = "USD,SGD,CNY", client: httpx.Client | None = None) -> dict | None:
    now = time.time()
    if _cache["data"] and now - _cache["at"] < TTL:
        return _cache["data"]
    try:
        c = client or httpx.Client(timeout=8)
        r = c.get(URL, params={"base": "MYR", "symbols": symbols})
        r.raise_for_status()
        j = r.json()
        data = {"source": "frankfurter.dev", "date": j["date"], "base": j["base"], "rates": j["rates"]}
    except Exception:
        return None
    _cache.update(at=now, data=data)
    return data


def to_myr(amount: float, currency: str, rates: dict) -> float:
    """Convert an amount in `currency` to MYR using rates quoted as 1 MYR = x currency."""
    if currency == "MYR":
        return amount
    return round(amount / rates["rates"][currency], 2)
