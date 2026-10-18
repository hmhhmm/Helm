"""Mock bank ("Demo bank"). Accepts an instruction with a scoped, expiring key, returns a receipt,
and rejects anything the key does not cover. Not a real bank; nothing here moves real money."""
import base64
import hashlib
import hmac
import json
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.audit import now_iso
from helm.config import BANK_SIGNING_SECRET
from helm.models import BankLedger

KEY_TTL_SECONDS = 300


def _sign(body: bytes) -> str:
    return hmac.new(BANK_SIGNING_SECRET.encode(), body, hashlib.sha256).hexdigest()


def mint_key(*, to_account: str, max_amount: float, scope: str, ttl: int = KEY_TTL_SECONDS, now: float | None = None) -> str:
    """A key that can pay ONE destination account up to ONE amount, once, for a few minutes."""
    claims = {"to": to_account, "max": round(max_amount, 2), "scope": scope, "exp": (now or time.time()) + ttl, "nonce": uuid.uuid4().hex[:12]}
    body = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode())
    return f"{body.decode()}.{_sign(body)}"


def _verify(key: str, now: float | None = None) -> tuple[dict | None, str | None]:
    try:
        body, sig = key.rsplit(".", 1)
    except ValueError:
        return None, "malformed key"
    if not hmac.compare_digest(sig, _sign(body.encode())):
        return None, "bad signature"
    claims = json.loads(base64.urlsafe_b64decode(body.encode()))
    if (now or time.time()) > claims["exp"]:
        return None, "key expired"
    return claims, None


def submit(session: Session, *, key: str, instruction_id: str, from_account: str, to_account: str,
           amount: float, scope: str, now: float | None = None) -> dict:
    claims, err = _verify(key, now)
    if err is None:
        if claims["scope"] != scope:
            err = "key is scoped to a different payment"
        elif claims["to"] != to_account:
            err = "key does not cover this destination account"
        elif amount > claims["max"] + 0.005:
            err = "amount is above what the key covers"
        else:
            used = session.execute(select(BankLedger).where(BankLedger.reason == f"nonce:{claims['nonce']}")).first()
            if used:
                err = "key already used"
    status = "rejected" if err else "accepted"
    session.add(BankLedger(
        instruction_id=instruction_id, ts=now_iso(), from_account=from_account, to_account=to_account,
        amount=amount, status=status, reason=err or f"nonce:{claims['nonce']}",
    ))
    session.flush()
    return {
        "receipt_id": "rcpt_" + uuid.uuid4().hex[:10], "instruction_id": instruction_id, "status": status,
        "reason": err, "amount": amount, "to_account": to_account, "bank": "Demo bank",
    }
