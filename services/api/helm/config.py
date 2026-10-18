import os
from pathlib import Path


def _load_dotenv() -> None:
    """Tiny .env reader (no dependency). Real environment variables always win."""
    here = Path.cwd().resolve()
    for d in [here, *here.parents][:4]:
        f = d / ".env"
        if f.is_file():
            for line in f.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


_load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./helm.db")
LLM_MODE = os.getenv("LLM_MODE", "fixtures")  # fixtures | live
BANK_SIGNING_SECRET = os.getenv("BANK_SIGNING_SECRET", "dev-only-secret")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
SEED = 2026
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
DEMO_RESET_MINUTES = int(os.getenv("DEMO_RESET_MINUTES", "20"))
RESERVE_APY = 0.025  # illustrative, used only for the "estimated interest" label
