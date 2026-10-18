import time

import pytest
from sqlalchemy import text

from helm import audit
from helm.bank import service as bank
from helm.db import engine
from helm.models import AuditLog


def test_chain_verifies_after_seed(session):
    r = audit.verify_chain(session)
    assert r["ok"] and r["checked"] > 5


def test_audit_log_is_append_only_for_the_application(session):
    with pytest.raises(Exception, match="append-only"):
        with engine.begin() as conn:
            conn.execute(text("UPDATE audit_log SET event = 'x' WHERE id = 1"))
    with pytest.raises(Exception, match="append-only"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM audit_log WHERE id = 1"))


def test_tampering_breaks_the_chain_and_names_the_row(fresh, session):
    out = audit.tamper_for_demo()
    session.expire_all()
    r = audit.verify_chain(session)
    assert not r["ok"] and r["broken_at"] == out["tampered"] and "contents" in r["reason"]


def test_deleted_row_is_detected(fresh, session):
    with engine.begin() as conn:
        from helm.db import drop_audit_triggers, install_audit_triggers
        drop_audit_triggers(conn)
        conn.execute(text("DELETE FROM audit_log WHERE id = 3"))
        install_audit_triggers(conn)
    session.expire_all()
    r = audit.verify_chain(session)
    assert not r["ok"] and r["broken_at"] == 3


def test_hash_is_sha256_of_prev_hash_plus_canonical_row(session):
    rows = session.query(AuditLog).order_by(AuditLog.id).limit(3).all()
    a, b = rows[0], rows[1]
    assert b.prev_hash == a.hash
    row = {"id": b.id, "ts": b.ts, "actor": b.actor, "event": b.event, "payload": b.payload}
    assert audit.row_hash(a.hash, row) == b.hash


# ---- the Demo bank ------------------------------------------------------------------------
def _submit(session, key, **kw):
    base = dict(instruction_id="ins_t", from_account="operating", to_account="ACC-1", amount=100.0, scope="p1")
    base.update(kw)
    return bank.submit(session, key=key, **base)


def test_bank_accepts_a_payment_the_key_covers(session):
    k = bank.mint_key(to_account="ACC-1", max_amount=100, scope="p1")
    assert _submit(session, k)["status"] == "accepted"


def test_bank_rejects_anything_the_key_does_not_cover(session):
    k = bank.mint_key(to_account="ACC-1", max_amount=100, scope="p1")
    assert "destination" in _submit(session, k, to_account="ACC-EVIL")["reason"]
    assert "above" in _submit(session, k, amount=100.01)["reason"]
    assert "different payment" in _submit(session, k, scope="p2")["reason"]


def test_bank_rejects_expired_forged_and_reused_keys(session):
    old = bank.mint_key(to_account="ACC-1", max_amount=100, scope="p1", now=time.time() - 1000)
    assert _submit(session, old)["reason"] == "key expired"
    k = bank.mint_key(to_account="ACC-1", max_amount=100, scope="p1")
    forged = k[:-4] + "0000"
    assert _submit(session, forged)["reason"] == "bad signature"
    assert _submit(session, k)["status"] == "accepted"
    assert _submit(session, k)["reason"] == "key already used"


# ---- database-level guarantees (Postgres only) -----------------------------------------------
def test_agent_role_cannot_write_rules_or_edit_the_audit_log():
    from helm.db import IS_SQLITE
    if IS_SQLITE:
        pytest.skip("role grants are a Postgres feature")
    with engine.connect() as conn:
        conn.execute(text("SET ROLE helm_agent"))
        assert conn.execute(text("SELECT min_balance FROM rules")).scalar_one() > 0
        for stmt in ("UPDATE rules SET min_balance = 0", "DELETE FROM rules", "UPDATE audit_log SET event = 'x'", "DELETE FROM audit_log"):
            with pytest.raises(Exception, match="permission denied|append-only"):
                conn.execute(text(stmt))
            conn.rollback()
            conn.execute(text("SET ROLE helm_agent"))
