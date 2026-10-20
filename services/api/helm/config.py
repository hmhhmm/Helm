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

# On-chain audit anchor (optional). All three must be set to anchor to a real network.
ANCHOR_RPC_URL = os.getenv("ANCHOR_RPC_URL", "")
ANCHOR_PRIVATE_KEY = os.getenv("ANCHOR_PRIVATE_KEY", "")  # a throwaway test network key; never a real wallet
ANCHOR_CONTRACT = os.getenv("ANCHOR_CONTRACT", "")
ANCHOR_EXPLORER_TX = os.getenv("ANCHOR_EXPLORER_TX", "https://sepolia.etherscan.io/tx/")

# Owner login. The default passcode is for the public synthetic demo only; set your own anywhere else.
OWNER_PASSCODE = os.getenv("OWNER_PASSCODE", "helm-demo")
OWNER_TOKEN_SECRET = os.getenv("OWNER_TOKEN_SECRET", BANK_SIGNING_SECRET + "-owner")

# Language model (optional, used only with LLM_MODE=live). Gemini is the default provider when its key is set.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")  # gemini | anthropic | empty = pick from the keys that exist
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
ANCHOR_FROM_BLOCK = int(os.getenv("ANCHOR_FROM_BLOCK", "0"))  # the block the contract was deployed in; logs are read from here

# Bank. demo = the built in simulation. wise = the real Wise sandbox (test money, needs WISE_API_KEY).
BANK_PROVIDER = os.getenv("BANK_PROVIDER", "wise" if os.getenv("WISE_API_KEY") else "demo")
WISE_API_KEY = os.getenv("WISE_API_KEY", "")
WISE_BASE_URL = os.getenv("WISE_BASE_URL", "https://api.wise-sandbox.com")
WISE_PROFILE_ID = int(os.getenv("WISE_PROFILE_ID", "0") or 0)
WISE_SOURCE_CURRENCY = os.getenv("WISE_SOURCE_CURRENCY", "GBP")  # the currency of the sandbox test balance
BANK_LABEL = {"demo": "Bank", "wise": "Wise sandbox"}.get(BANK_PROVIDER, "Bank")
