#!/usr/bin/env python3
"""Deploys AuditAnchor to an in process EVM (py-evm), anchors the Helm audit head, verifies it, then tampers
with one audit row and shows verification failing. Produces real transaction hashes on a LOCAL test chain.
This is a rehearsal. The public network run is scripts/deploy_anchor.py. Output: docs/evidence/local-chain.txt"""
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/demo.db"
sys.path.insert(0, str(ROOT / "services" / "api"))

from sqlalchemy import text  # noqa: E402
from web3 import EthereumTesterProvider, Web3  # noqa: E402

from helm import anchor  # noqa: E402
from helm.bootstrap import reset_demo  # noqa: E402
from helm.db import SessionLocal, drop_audit_triggers, engine, install_audit_triggers  # noqa: E402

out = []


def say(s):
    print(s)
    out.append(s)


commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
say(f"produced {datetime.now(timezone.utc).isoformat()} at commit {commit}")
reset_demo()
w3 = Web3(EthereumTesterProvider())
art = anchor.load_artifact()
dep = w3.eth.accounts[0]
tx = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"]).constructor().transact({"from": dep})
rc = w3.eth.wait_for_transaction_receipt(tx)
say(f"LOCAL TEST CHAIN (in process EVM, not a public network). chain id {w3.eth.chain_id}")
say(f"deploy tx  0x{bytes(tx).hex().removeprefix('0x')}  contract {rc['contractAddress']}")
client = anchor.ChainClient(w3, rc["contractAddress"], account=dep)
with SessionLocal() as s:
    rows = anchor.anchor_now(s, client)
    s.commit()
    for r in rows:
        say(f"{r.kind:6} anchor  seq/version {r.seq:<4} hash {r.hash}  tx {r.tx_hash}  block {r.block_number}")
    say(f"verify on untouched log   -> {anchor.verify_anchors(s, client)['ok']}")
    with engine.begin() as c:
        drop_audit_triggers(c)
        c.execute(text("UPDATE audit_log SET event = event || ' (edited)' WHERE id = 5"))
        install_audit_triggers(c)
    s.expire_all()
    res = anchor.verify_anchors(s, client)
    say(f"verify after editing row 5 -> {res['ok']}  (on chain {res['anchors'][0]['on_chain']}, database matches {res['anchors'][0]['database_matches']})")
(ROOT / "docs" / "evidence" / "local-chain.txt").write_text("\n".join(out) + "\n")
