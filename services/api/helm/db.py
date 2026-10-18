from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from helm.config import DATABASE_URL

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Idempotent: creates missing tables only."""
    from helm import models  # noqa: F401  (registers tables)

    Base.metadata.create_all(engine)


def get_session():
    with SessionLocal() as session:
        yield session
