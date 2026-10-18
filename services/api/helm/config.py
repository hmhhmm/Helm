import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./helm.db")
LLM_MODE = os.getenv("LLM_MODE", "fixtures")  # fixtures | live
BANK_SIGNING_SECRET = os.getenv("BANK_SIGNING_SECRET", "dev-only-secret")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
SEED = 2026
