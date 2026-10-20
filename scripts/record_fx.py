#!/usr/bin/env python3
"""Calls the real Frankfurter API and saves the raw response with a timestamp: docs/evidence/fx-frankfurter.json"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
url = "https://api.frankfurter.dev/v1/latest"
r = httpx.get(url, params={"base": "MYR", "symbols": "USD,SGD,CNY"}, timeout=15)
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
out = {"produced_at": datetime.now(timezone.utc).isoformat(), "git_commit": commit, "request": str(r.request.url), "http_status": r.status_code, "response": r.json()}
(ROOT / "docs" / "evidence" / "fx-frankfurter.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
