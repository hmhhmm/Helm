from sqlalchemy import select

from helm.db import SessionLocal, init_db, reset_db
from helm.models import Rules
from helm.pipeline import run_pipeline
from helm.seed import seed_database


def reset_demo() -> None:
    reset_db()
    with SessionLocal() as s:
        seed_database(s)
        run_pipeline(s, trigger="seed")
        s.commit()


def ensure_seeded() -> bool:
    init_db()
    with SessionLocal() as s:
        if s.execute(select(Rules)).first():
            return False
    reset_demo()
    return True
