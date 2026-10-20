"""On-chain anchor for the audit log and the owner's cash policy.

Only hashes are written, never business data. The contract (contracts/AuditAnchor.sol) stores nothing
and emits one event per anchor. To verify, this module recomputes the hash chain from the database,
reads the events sent by the expected anchor address, and compares the two.
What the anchor proves: the log is unchanged since it was anchored. What it does not prove: that the
original events were true. Anyone can call the contract, so only events from the expected sender count.
"""
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from helm import config
from helm.audit import GENESIS, append, canonical_json, now_iso, row_hash
from helm.models import Anchor, AuditLog, Rules

ARTIFACT = Path(__file__).resolve().parents[3] / "contracts" / "AuditAnchor.json"


def load_artifact() -> dict:
    return json.loads(ARTIFACT.read_text())


# --- what gets anchored ---------------------------------------------------------------
def audit_head(session: Session) -> tuple[int, str] | None:
    last = session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    return (last.id, last.hash) if last else None


def recompute_hash_at(session: Session, seq: int) -> str | None:
    """Recompute the chain from row 1 to `seq` using the stored row contents (not the stored hashes)."""
    prev = GENESIS
    rows = session.execute(select(AuditLog).where(AuditLog.id <= seq).order_by(AuditLog.id)).scalars().all()
    if not rows or rows[-1].id != seq:
        return None
    for r in rows:
        prev = row_hash(prev, {"id": r.id, "ts": r.ts, "actor": r.actor, "event": r.event, "payload": r.payload})
    return prev


def policy_version(session: Session) -> int:
    return len(session.execute(select(AuditLog.id).where(AuditLog.event == "rules.changed")).all())


def policy_hash(session: Session) -> str:
    r = session.get(Rules, 1)
    doc = {
        "min_balance": r.min_balance, "risk_tolerance": r.risk_tolerance,
        "approval_limit": r.approval_limit, "protected_payees": sorted(r.protected_payees),
        "daily_cap": r.daily_cap, "monthly_cap": r.monthly_cap,
        "mandate_expires": r.mandate_expires.isoformat() if r.mandate_expires else None,
    }
    return hashlib.sha256(canonical_json(doc).encode()).hexdigest()


def _b32(hex_hash: str) -> bytes:
    return bytes.fromhex(hex_hash)


# --- chain access -----------------------------------------------------------------------
class ChainClient:
    """Thin wrapper over web3. In production it points at a test network; in tests at an in-process EVM."""

    def __init__(self, w3: Any, contract_address: str, private_key: str | None = None, account: str | None = None):
        art = load_artifact()
        self.w3 = w3
        self.contract = w3.eth.contract(address=w3.to_checksum_address(contract_address), abi=art["abi"])
        self.account = account
        self.key = private_key
        if private_key and not account:
            self.account = w3.eth.account.from_key(private_key).address

    @classmethod
    def from_env(cls) -> "ChainClient | None":
        if not (config.ANCHOR_RPC_URL and config.ANCHOR_PRIVATE_KEY and config.ANCHOR_CONTRACT):
            return None
        from web3 import Web3

        return cls(Web3(Web3.HTTPProvider(config.ANCHOR_RPC_URL, request_kwargs={"timeout": 30})),
                   config.ANCHOR_CONTRACT, config.ANCHOR_PRIVATE_KEY)

    @property
    def chain_id(self) -> int:
        return int(self.w3.eth.chain_id)

    def _send(self, fn) -> dict:
        if self.key:
            tx = fn.build_transaction({
                "from": self.account, "nonce": self.w3.eth.get_transaction_count(self.account),
                "chainId": self.chain_id,
            })
            signed = self.w3.eth.account.sign_transaction(tx, self.key)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            tx_hash = self.w3.eth.send_raw_transaction(raw)
        else:  # in-process test chain with unlocked accounts
            tx_hash = fn.transact({"from": self.account})
        rcpt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        return {"tx_hash": "0x" + bytes(tx_hash).hex().removeprefix("0x"), "block": int(rcpt["blockNumber"]), "ok": rcpt["status"] == 1}

    def anchor(self, seq: int, head_hash: str) -> dict:
        return self._send(self.contract.functions.anchor(seq, _b32(head_hash)))

    def anchor_policy(self, version: int, phash: str) -> dict:
        return self._send(self.contract.functions.anchorPolicy(version, _b32(phash)))

    def anchored_events(self) -> list[dict]:
        return [{"seq": int(e["args"]["seq"]), "hash": bytes(e["args"]["headHash"]).hex(), "by": e["args"]["by"], "tx": "0x" + bytes(e["transactionHash"]).hex().removeprefix("0x")}
                for e in self.contract.events.Anchored().get_logs(from_block=0)]

    def policy_events(self) -> list[dict]:
        return [{"version": int(e["args"]["version"]), "hash": bytes(e["args"]["policyHash"]).hex(), "by": e["args"]["by"], "tx": "0x" + bytes(e["transactionHash"]).hex().removeprefix("0x")}
                for e in self.contract.events.PolicyAnchored().get_logs(from_block=0)]


# --- anchoring and verifying ---------------------------------------------------------------
def anchor_now(session: Session, chain: ChainClient) -> list[Anchor]:
    """Anchor the current audit head and the current policy hash. Records each result and logs it.
    A network failure is logged and never raised, so the app keeps working."""
    out: list[Anchor] = []
    head = audit_head(session)
    if head is None:
        return out
    seq, h = head
    pv, ph = policy_version(session), policy_hash(session)
    for kind, n, hx, send in (("audit", seq, h, chain.anchor), ("policy", pv, ph, chain.anchor_policy)):
        try:
            res = send(n, hx)
            status = "confirmed" if res["ok"] else "failed"
        except Exception as exc:
            append(session, "anchor", "anchor.failed", {"kind": kind, "seq": n, "error": str(exc)[:200]})
            continue
        row = Anchor(kind=kind, seq=n, hash=hx, tx_hash=res["tx_hash"], block_number=res["block"], chain_id=chain.chain_id,
                     contract=chain.contract.address, sender=chain.account, status=status, created_at=now_iso())
        session.add(row)
        out.append(row)
    session.flush()
    for row in out:
        append(session, "anchor", "anchor.sent", {"kind": row.kind, "seq": row.seq, "hash": row.hash, "tx_hash": row.tx_hash, "chain_id": row.chain_id})
    return out


def verify_anchors(session: Session, chain: ChainClient) -> dict:
    """Compare every recorded audit anchor with the chain and with a hash recomputed from the database."""
    events = {(e["seq"], e["hash"]) for e in chain.anchored_events() if e["by"].lower() == (chain.account or "").lower()}
    results = []
    for a in session.execute(select(Anchor).where(Anchor.kind == "audit").order_by(Anchor.id)).scalars():
        recomputed = recompute_hash_at(session, a.seq)
        on_chain = (a.seq, a.hash) in events
        results.append({"seq": a.seq, "tx_hash": a.tx_hash, "on_chain": on_chain, "database_matches": recomputed == a.hash,
                        "ok": on_chain and recomputed == a.hash})
    return {"ok": bool(results) and all(r["ok"] for r in results), "checked": len(results), "anchors": results,
            "expected_sender": chain.account}


def auto_anchor(session: Session) -> int:
    """Called after a pipeline run. Does nothing unless the anchor is configured."""
    chain = ChainClient.from_env()
    if chain is None:
        return 0
    try:
        return len(anchor_now(session, chain))
    except Exception as exc:  # never let anchoring break a run
        append(session, "anchor", "anchor.failed", {"error": str(exc)[:200]})
        return 0
