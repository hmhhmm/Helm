#!/usr/bin/env python3
"""Runs Helm's pipeline with BANK_PROVIDER=wise against the real Wise sandbox and writes docs/evidence/sandbox-bank-log.txt.
Run from services/api with the venv: BANK_PROVIDER=wise WISE_API_KEY=... python ../../scripts/run_wise_evidence.py
Sandbox test money only. The log holds request paths, statuses and Wise's own ids. It never holds the key."""
import os, sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/wise_ev.db")
os.environ.setdefault("LLM_MODE", "fixtures")
os.environ["ANCHOR_RPC_URL"] = ""
sys.path.insert(0, ".")
from fastapi.testclient import TestClient  # noqa: E402
from helm import config  # noqa: E402
from helm.bank import wise  # noqa: E402
from helm.main import app  # noqa: E402

assert config.BANK_PROVIDER == "wise" and config.WISE_API_KEY, "set BANK_PROVIDER=wise and WISE_API_KEY"
out = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "sandbox-bank-log.txt"
with TestClient(app) as c:
    tok = c.post("/auth/login", json={"passcode": os.environ.get("OWNER_PASSCODE", "helm-demo")}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    c.post("/sim/reset")
    receipts = []
    for _ in range(4):
        c.post("/sim/advance-week")
        receipts = [r for r in c.get("/bank/ledger").json().get("entries", [])]
    ledger = c.get("/bank/ledger").json()
lines = [f"Helm to Wise sandbox, {datetime.now(timezone.utc).isoformat()}",
         "Wise sandbox, test money only. Payee bank details are synthetic test numbers. A personal token cannot fund a transfer by API, so the sandbox simulation steps move each transfer to outgoing_payment_sent.", ""]
for e in wise.CALL_LOG:
    lines.append(f"{e['at']}  {e['method']:4} {e['path']}  HTTP {e['http_status']}  id={e['provider_id']}  status={e['provider_status']}  {e['note']}")
lines += ["", "Helm ledger:", str(ledger)[:3000]]
out.write_text("\n".join(lines) + "\n")
print("\n".join(lines[:60]))
