import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./helm.db")
LLM_MODE = os.getenv("LLM_MODE", "fixtures")  # fixtures | live
BANK_SIGNING_SECRET = os.getenv("BANK_SIGNING_SECRET", "dev-only-secret")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
SEED = 2026
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
DEMO_RESET_MINUTES = int(os.getenv("DEMO_RESET_MINUTES", "20"))
RESERVE_APY = 0.025  # illustrative, used only for the "estimated interest" label
