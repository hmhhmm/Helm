from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from helm.config import DATABASE_URL

IS_SQLITE = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False, "timeout": 30} if IS_SQLITE else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# --- append-only audit log -------------------------------------------------
_SQLITE_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
       BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
       BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END""",
]
_PG_TRIGGERS = [
    """CREATE OR REPLACE FUNCTION audit_append_only() RETURNS trigger AS $$
       BEGIN RAISE EXCEPTION 'audit_log is append-only'; END; $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS audit_no_update ON audit_log",
    "DROP TRIGGER IF EXISTS audit_no_delete ON audit_log",
    """CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_log
       FOR EACH ROW EXECUTE FUNCTION audit_append_only()""",
    """CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_log
       FOR EACH ROW EXECUTE FUNCTION audit_append_only()""",
]


def install_audit_triggers(conn) -> None:
    for stmt in _SQLITE_TRIGGERS if IS_SQLITE else _PG_TRIGGERS:
        conn.execute(text(stmt))


def drop_audit_triggers(conn) -> None:
    if IS_SQLITE:
        conn.execute(text("DROP TRIGGER IF EXISTS audit_no_update"))
        conn.execute(text("DROP TRIGGER IF EXISTS audit_no_delete"))
    else:
        conn.execute(text("DROP TRIGGER IF EXISTS audit_no_update ON audit_log"))
        conn.execute(text("DROP TRIGGER IF EXISTS audit_no_delete ON audit_log"))


_PG_ROLES = [
    "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'helm_agent') THEN CREATE ROLE helm_agent NOLOGIN; END IF; END $$",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO helm_agent",
    # agents hand off through these records ...
    "GRANT INSERT, UPDATE, DELETE ON documents, invoices, bills, cash_range, chase_ideas, bill_plan, proposals, decisions, agent_runs, agent_steps, alerts TO helm_agent",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO helm_agent",
    # ... but never write the owner's rules, and can only append to the audit log
    "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON rules FROM helm_agent",
    "GRANT INSERT ON audit_log TO helm_agent",
    "REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM helm_agent",
]


def install_pg_roles(conn) -> None:
    """Postgres only: a database role for agents with read-only access to the owner's rules."""
    if IS_SQLITE:
        return
    for stmt in _PG_ROLES:
        conn.execute(text(stmt))


def _add_missing_columns(conn) -> None:
    """Tiny forward-only migration: add columns introduced after a database was first created."""
    from sqlalchemy import inspect

    insp = inspect(conn)
    if insp.has_table("rules"):
        have = {c["name"] for c in insp.get_columns("rules")}
        for col, ddl in (("daily_cap", "FLOAT"), ("monthly_cap", "FLOAT"), ("mandate_expires", "DATE")):
            if col not in have:
                conn.execute(text(f"ALTER TABLE rules ADD COLUMN {col} {ddl}"))


def init_db() -> None:
    """Idempotent: creates missing tables, installs the append-only triggers and the agent role."""
    from helm import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        _add_missing_columns(conn)
        install_audit_triggers(conn)
        install_pg_roles(conn)


def reset_db() -> None:
    from helm import models  # noqa: F401

    with engine.begin() as conn:
        drop_audit_triggers(conn) if _table_exists(conn) else None
    Base.metadata.drop_all(engine)
    init_db()


def _table_exists(conn) -> bool:
    from sqlalchemy import inspect

    return inspect(conn).has_table("audit_log")


def get_session():
    with SessionLocal() as session:
        yield session
