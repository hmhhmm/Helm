"""Owner authentication. Every route that changes state (policy, kill switch, approvals, simulator, anchor)
requires a signed, expiring owner token. Reading screens stays open so a judge can look around the demo.

The passcode comes from OWNER_PASSCODE. In the public demo it is shown on the login dialog on purpose, because the
data is synthetic. In any real deployment set a private passcode (and replace this with a proper identity provider).
"""
import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException

from helm import config

TOKEN_TTL_SECONDS = 8 * 3600
_attempts: dict[str, deque] = defaultdict(deque)


def _sign(body: bytes) -> str:
    return hmac.new(config.OWNER_TOKEN_SECRET.encode(), body, hashlib.sha256).hexdigest()


def issue_token(now: float | None = None) -> dict:
    exp = int((now or time.time()) + TOKEN_TTL_SECONDS)
    body = base64.urlsafe_b64encode(json.dumps({"sub": "owner", "exp": exp}).encode())
    return {"token": f"{body.decode()}.{_sign(body)}", "expires": exp}


def verify_token(token: str | None, now: float | None = None) -> bool:
    if not token or "." not in token:
        return False
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body.encode())):
        return False
    try:
        claims = json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return False
    return claims.get("sub") == "owner" and (now or time.time()) < claims.get("exp", 0)


def check_passcode(passcode: str, client: str = "local", now: float | None = None) -> bool:
    """Constant-time comparison with a small rate limit (5 tries a minute per client)."""
    t = now or time.time()
    q = _attempts[client]
    while q and t - q[0] > 60:
        q.popleft()
    if len(q) >= 5:
        raise HTTPException(429, "Too many attempts. Wait a minute.")
    q.append(t)
    ok = hmac.compare_digest(passcode.encode(), config.OWNER_PASSCODE.encode())
    if ok:
        q.clear()
    return ok


def require_owner(authorization: str | None = Header(default=None)) -> None:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if not verify_token(token):
        raise HTTPException(401, "Owner login required")
