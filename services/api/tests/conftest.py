import os
import tempfile

# one throw-away database per test session; must be set before helm is imported
_tmp = tempfile.mkdtemp(prefix="helm-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["LLM_MODE"] = "fixtures"

import pytest  # noqa: E402

from helm.bootstrap import reset_demo  # noqa: E402
from helm.db import SessionLocal  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seeded():
    reset_demo()


@pytest.fixture()
def fresh():
    """Reset to the seeded start before tests that change the world."""
    reset_demo()
    yield


@pytest.fixture()
def session():
    with SessionLocal() as s:
        yield s
        s.rollback()
