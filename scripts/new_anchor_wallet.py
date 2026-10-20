#!/usr/bin/env python3
"""Creates a NEW throwaway wallet for the test network anchor and stores its key in .env (which git ignores).
Prints only the public address, so you can fund it from a faucet. Never reuse a wallet that holds real value."""
import sys
from pathlib import Path

from eth_account import Account

env = Path(__file__).resolve().parents[1] / ".env"
text = env.read_text() if env.exists() else ""
if "ANCHOR_PRIVATE_KEY=" in text and not text.split("ANCHOR_PRIVATE_KEY=")[1].startswith(("\n", "0x...")):
    sys.exit("A key is already set in .env. Delete that line first if you really want a new wallet.")
acct = Account.create()
lines = [l for l in text.splitlines() if not l.startswith(("ANCHOR_PRIVATE_KEY=", "ANCHOR_RPC_URL="))]
lines += ["ANCHOR_RPC_URL=https://ethereum-sepolia-rpc.publicnode.com", f"ANCHOR_PRIVATE_KEY={acct.key.hex()}"]
env.write_text("\n".join(lines) + "\n")
print("Throwaway wallet created. Fund THIS address with Sepolia test ETH from a faucet:")
print(acct.address)
