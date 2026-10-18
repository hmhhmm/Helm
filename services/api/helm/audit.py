"""Hash-chained, append-only audit log.

hash = sha256(prev_hash + canonical_json(row)), row = {id, ts, actor, event, payload}.
"""
import hashlib
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from helm.db import IS_SQLITE, drop_audit_triggers, engine, install_audit_triggers
from helm.models import AuditLog

GENESIS = "0" * 64
_lock = threading.Lock()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def row_hash(prev_hash: str, row: dict) -> str:
    return hashlib.sha256((prev_hash + canonical_json(row)).encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def append(session: Session, actor: str, event: str, payload: dict) -> AuditLog:
    """Append one row. The caller's transaction commits it."""
    payload = json.loads(canonical_json(payload))  # normalise to JSON-native types
    with _lock:
        if not IS_SQLITE:
            session.execute(text("SELECT pg_advisory_xact_lock(2026)"))
        last = session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
        prev_hash = last.hash if last else GENESIS
        next_id = (last.id + 1) if last else 1
        ts = now_iso()
        row = {"id": next_id, "ts": ts, "actor": actor, "event": event, "payload": payload}
        entry = AuditLog(
            id=next_id, ts=ts, actor=actor, event=event, payload=payload,
            prev_hash=prev_hash, hash=row_hash(prev_hash, row),
        )
        session.add(entry)
        session.flush()
    return entry


def verify_chain(session: Session) -> dict:
    """Recompute every hash. Returns {ok, checked, broken_at, reason}."""
    prev = GENESIS
    checked = 0
    rows = session.execute(select(AuditLog).order_by(AuditLog.id)).scalars().all()
    expected_id = 1
    for r in rows:
        if r.id != expected_id:
            return {"ok": False, "checked": checked, "broken_at": expected_id, "reason": f"row {expected_id} is missing"}
        if r.prev_hash != prev:
            return {"ok": False, "checked": checked, "broken_at": r.id, "reason": "link to the previous row does not match"}
        row = {"id": r.id, "ts": r.ts, "actor": r.actor, "event": r.event, "payload": r.payload}
        if row_hash(prev, row) != r.hash:
            return {"ok": False, "checked": checked, "broken_at": r.id, "reason": "row contents do not match its hash"}
        prev = r.hash
        checked += 1
        expected_id += 1
    return {"ok": True, "checked": checked, "broken_at": None, "reason": None}


def tamper_for_demo(row_id: int | None = None) -> dict:
    """Simulates someone with database admin rights editing history.

    The append-only triggers stop the application role. An attacker with admin rights could drop
    them; the hash chain is what still catches the edit.
    """
    with engine.begin() as conn:
        if row_id is None:
            n = conn.execute(text("SELECT count(*) FROM audit_log")).scalar_one()
            if n == 0:
                return {"tampered": None}
            row_id = max(1, n // 2)
        drop_audit_triggers(conn)
        conn.execute(text("UPDATE audit_log SET event = event || ' (edited)' WHERE id = :i"), {"i": row_id})
        install_audit_triggers(conn)
    return {"tampered": row_id}
