"""Wise sandbox adapter. Pays through the real Wise sandbox API with test money.

What is real: the quote, the recipient, the transfer and its status all come from Wise's sandbox servers, and every
provider id in the receipts is theirs. What is simulated: the sandbox is a test environment with no real money, the
payee bank details are synthetic test numbers, and a personal token cannot fund a transfer by API (HTTP 403), so the
sandbox's own simulation steps move a transfer from created to outgoing_payment_sent. The Helm account is a GBP test
balance, so a Malaysian ringgit payment is quoted from GBP with a fixed ringgit amount.
"""
import hashlib
import re
import time
import uuid
from datetime import datetime, timezone

import httpx

from helm import config

CALL_LOG: list[dict] = []  # request path, status and the provider's own ids. Never holds the key.
_recipients: dict[str, int] = {}
_profile: dict = {}


class WiseError(Exception):
    pass


def _client(client: httpx.Client | None) -> httpx.Client:
    return client or httpx.Client(timeout=30)


def _headers() -> dict:
    if not config.WISE_API_KEY:
        raise WiseError("WISE_API_KEY is not set")
    return {"Authorization": f"Bearer {config.WISE_API_KEY}", "Accept-Minor-Version": "1", "Content-Type": "application/json"}


def _call(c: httpx.Client, method: str, path: str, json: dict | None = None, note: str = "") -> dict | list:
    url = config.WISE_BASE_URL.rstrip("/") + path
    try:
        r = c.request(method, url, headers=_headers(), json=json)
    except httpx.HTTPError as exc:
        raise WiseError(f"network error: {type(exc).__name__}") from None
    body = None
    try:
        body = r.json()
    except ValueError:
        pass
    CALL_LOG.append({
        "at": datetime.now(timezone.utc).isoformat(), "method": method, "path": path, "http_status": r.status_code, "note": note,
        "provider_id": (body or {}).get("id") if isinstance(body, dict) else None,
        "provider_status": (body or {}).get("status") if isinstance(body, dict) else None,
    })
    if r.status_code >= 300:
        msg = ""
        if isinstance(body, dict):
            msg = str(body.get("message") or body.get("error") or "")[:160]
        raise WiseError(f"wise HTTP {r.status_code} on {path}: {msg}")
    return body


def profile_id(c: httpx.Client) -> int:
    if config.WISE_PROFILE_ID:
        return config.WISE_PROFILE_ID
    if "id" not in _profile:
        profiles = _call(c, "GET", "/v2/profiles", note="find profile")
        if not profiles:
            raise WiseError("no Wise profile found")
        _profile["id"] = int(profiles[0]["id"])
    return _profile["id"]


def _test_account_number(account_ref: str) -> str:
    """A Malaysian Wise recipient needs exactly 12 digits. Helm's references are not bank numbers, so derive a stable test number."""
    return str(int(hashlib.sha256(account_ref.encode()).hexdigest(), 16))[:12]


def recipient_for(c: httpx.Client, pid: int, payee: str, account_ref: str) -> int:
    key = f"{payee}|{account_ref}"
    if key not in _recipients:
        body = {
            "currency": "MYR", "type": "malaysian", "profile": pid, "accountHolderName": re.sub(r"[^A-Za-z0-9 .,&()'-]", "", payee)[:60] or "Payee",
            "ownedByCustomer": False, "details": {"legalType": "BUSINESS", "swiftCode": "MBBEMYKL", "accountNumber": _test_account_number(account_ref)},
        }
        _recipients[key] = int(_call(c, "POST", "/v1/accounts", body, note=f"recipient for {payee}")["id"])
    return _recipients[key]


def pay(payee: str, account_ref: str, amount_myr: float, reference: str, client: httpx.Client | None = None) -> dict:
    """Quote, recipient, transfer, then (sandbox only) the simulation steps. Returns the provider's own ids and status."""
    c = _client(client)
    pid = profile_id(c)
    quote = _call(c, "POST", f"/v3/profiles/{pid}/quotes", {"sourceCurrency": config.WISE_SOURCE_CURRENCY, "targetCurrency": "MYR", "targetAmount": round(amount_myr, 2)}, note="quote")
    rid = recipient_for(c, pid, payee, account_ref)
    transfer = _call(c, "POST", "/v1/transfers", {
        "targetAccount": rid, "quoteUuid": quote["id"], "customerTransactionId": str(uuid.uuid4()),
        "details": {"reference": reference[:35] or "Helm payment"},
    }, note=f"transfer to {payee}")
    tid = int(transfer["id"])
    status = transfer.get("status")
    if "sandbox" in config.WISE_BASE_URL:
        for step in ("processing", "funds_converted", "outgoing_payment_sent"):
            status = _call(c, "GET", f"/v1/simulation/transfers/{tid}/{step}", note=f"sandbox simulation {step}").get("status", status)
    final = _call(c, "GET", f"/v1/transfers/{tid}", note="read back status")
    return {
        "provider": "wise_sandbox", "transfer_id": tid, "status": final.get("status", status), "quote_id": quote["id"], "recipient_id": rid,
        "source_amount": final.get("sourceValue"), "source_currency": final.get("sourceCurrency"), "target_amount": final.get("targetValue"),
        "target_currency": final.get("targetCurrency"), "rate": final.get("rate"), "reference": final.get("reference"),
    }
