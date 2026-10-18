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


def init_db() -> None:
    """Idempotent: creates missing tables and (re)installs the append-only triggers."""
    from helm import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        install_audit_triggers(conn)


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
