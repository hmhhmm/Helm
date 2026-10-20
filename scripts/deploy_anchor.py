#!/usr/bin/env python3
"""Deploy AuditAnchor to a public test network and anchor the current Helm audit head and policy hash.

Run this on your own machine (it needs internet access to a test network RPC and a funded throwaway key).

  export ANCHOR_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com      # or any Sepolia / Base Sepolia RPC
  export ANCHOR_PRIVATE_KEY=0x...        # a NEW throwaway key holding only faucet test ETH. Never a real wallet.
  python scripts/deploy_anchor.py

It deploys the contract, anchors, verifies against the chain, and writes docs/evidence/onchain.json with the real
transaction hashes and explorer links. Re-running it deploys a new contract and appends to the same file's history.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from web3 import Web3  # noqa: E402

from helm import anchor  # noqa: E402
from helm.bootstrap import ensure_seeded  # noqa: E402
from helm.db import SessionLocal  # noqa: E402

EXPLORERS = {11155111: "https://sepolia.etherscan.io", 84532: "https://sepolia.basescan.org"}


def main() -> None:
    rpc, key = os.environ.get("ANCHOR_RPC_URL"), os.environ.get("ANCHOR_PRIVATE_KEY")
    if not rpc or not key:
        sys.exit("Set ANCHOR_RPC_URL and ANCHOR_PRIVATE_KEY first (see the docstring).")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        sys.exit("Cannot reach the RPC endpoint.")
    acct = w3.eth.account.from_key(key)
    chain_id = w3.eth.chain_id
    balance = w3.eth.get_balance(acct.address)
    print(f"chain id {chain_id}, sender {acct.address}, balance {w3.from_wei(balance, 'ether')} ETH")
    if balance == 0:
        sys.exit("The sender has no test ETH. Use a faucet first.")
    art = anchor.load_artifact()
    Contract = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
    tx = Contract.constructor().build_transaction({"from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address), "chainId": chain_id})
    signed = w3.eth.account.sign_transaction(tx, key)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    deploy_hash = w3.eth.send_raw_transaction(raw)
    rcpt = w3.eth.wait_for_transaction_receipt(deploy_hash, timeout=240)
    address = rcpt["contractAddress"]
    dh = "0x" + bytes(deploy_hash).hex().removeprefix("0x")
    print("deployed", address, "tx", dh)

    os.environ["ANCHOR_CONTRACT"] = address
    ensure_seeded()
    client = anchor.ChainClient(w3, address, private_key=key)
    with SessionLocal() as s:
        rows = anchor.anchor_now(s, client)
        s.commit()
        result = anchor.verify_anchors(s, client)
    base = EXPLORERS.get(chain_id, "")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {
        "produced_at": datetime.now(timezone.utc).isoformat(), "git_commit": commit,
        "network_chain_id": chain_id, "contract": address, "sender": acct.address, "deploy_tx": dh,
        "anchors": [{"kind": r.kind, "seq": r.seq, "hash": r.hash, "tx_hash": r.tx_hash, "block": r.block_number} for r in rows],
        "verify": result,
        "explorer": {"contract": f"{base}/address/{address}", "deploy_tx": f"{base}/tx/{dh}", "anchor_txs": [f"{base}/tx/{r.tx_hash}" for r in rows]},
    }
    path = ROOT / "docs" / "evidence" / "onchain.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print("\nSet ANCHOR_CONTRACT in .env to", address, "so the app keeps anchoring to this contract.")


if __name__ == "__main__":
    main()
