import threading

from sqlalchemy import select

from helm import config, live
from helm.db import SessionLocal, init_db, reset_db
from helm.models import Rules, SimState
from helm.pipeline import run_pipeline
from helm.seed import seed_database

# A reset drops and rebuilds every table. Requests that arrive in that window wait here instead of reading half a database.
_lock = threading.RLock()
_ready = False


def is_ready() -> bool:
    return _ready


def reset_demo() -> None:
    global _ready
    with _lock:
        _ready = False
        reset_db()
        with SessionLocal() as s:
            seed_database(s)
            run_pipeline(s, trigger="seed")
            if config.BANK_PROVIDER == "wise":
                # With a real bank connected, start with one payment waiting for the owner, ready to approve and send.
                live.enter_payment(s, "Ladang Kertas Utama", 1_200, "INV-2610-0088")
            s.commit()
        _ready = True


def ensure_seeded() -> bool:
    """Makes sure the database is seeded and complete. Returns True when it had to be rebuilt."""
    global _ready
    with _lock:
        if _ready:
            return False
        init_db()
        with SessionLocal() as s:
            complete = s.execute(select(Rules)).first() is not None and s.get(SimState, 1) is not None
        if complete:
            _ready = True
            return False
        reset_demo()
        return True
