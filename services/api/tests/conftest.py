import os
import tempfile

# one throw-away database per test session; must be set before helm is imported
_tmp = tempfile.mkdtemp(prefix="helm-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")  # set DATABASE_URL to run the suite on Postgres
os.environ["LLM_MODE"] = "fixtures"
# Tests must never touch a real network or spend a real key, even when .env holds them.
for _k in ("ANCHOR_RPC_URL", "ANCHOR_PRIVATE_KEY", "ANCHOR_CONTRACT", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ[_k] = ""
os.environ["ANCHOR_FROM_BLOCK"] = "0"

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


def owner_client():
    """A test client that is logged in as the owner (state changing routes need a token)."""
    from fastapi.testclient import TestClient

    from helm.auth import issue_token
    from helm.main import app

    return TestClient(app, headers={"Authorization": "Bearer " + issue_token()["token"]})
