"""On-chain anchor tests. They run against a real EVM (py-evm through eth-tester) in the same process,
so the contract bytecode in contracts/AuditAnchor.json is genuinely executed and real transaction hashes are produced.
The deploy to a public test network is done with scripts/deploy_anchor.py (see README)."""
import pytest
from sqlalchemy import text
from web3 import EthereumTesterProvider, Web3

from helm import anchor
from helm.audit import append, verify_chain
from helm.db import drop_audit_triggers, engine, install_audit_triggers
from helm.models import Anchor


@pytest.fixture()
def chain():
    w3 = Web3(EthereumTesterProvider())
    deployer, other = w3.eth.accounts[0], w3.eth.accounts[1]
    art = anchor.load_artifact()
    tx = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"]).constructor().transact({"from": deployer})
    address = w3.eth.wait_for_transaction_receipt(tx)["contractAddress"]
    client = anchor.ChainClient(w3, address, account=deployer)
    client.other = other
    return client


def test_contract_has_no_state_and_no_payable_functions():
    abi = anchor.load_artifact()["abi"]
    fns = [x for x in abi if x["type"] == "function"]
    assert {f["name"] for f in fns} == {"anchor", "anchorPolicy"}
    assert all(f["stateMutability"] == "nonpayable" for f in fns)
    assert not any(x["type"] in ("receive", "fallback") for x in abi)  # cannot receive funds


def test_contract_rejects_plain_value_transfers(chain):
    with pytest.raises(Exception):
        chain.w3.eth.send_transaction({"from": chain.account, "to": chain.contract.address, "value": 1})


def test_anchor_writes_the_head_hash_and_the_policy_hash(fresh, session, chain):
    rows = anchor.anchor_now(session, chain)
    session.commit()
    assert [r.kind for r in rows] == ["audit", "policy"]
    assert all(r.tx_hash.startswith("0x") and len(r.tx_hash) == 66 for r in rows)
    ev = chain.anchored_events()
    assert len(ev) == 1 and ev[0]["hash"] == rows[0].hash and ev[0]["seq"] == rows[0].seq
    pe = chain.policy_events()
    assert len(pe) == 1 and pe[0]["hash"] == anchor.policy_hash(session)


def test_only_hashes_reach_the_chain(fresh, session, chain):
    anchor.anchor_now(session, chain)
    w3 = chain.w3
    blob = b""
    for n in range(1, w3.eth.block_number + 1):
        for t in w3.eth.get_block(n, full_transactions=True)["transactions"]:
            blob += bytes(t.get("input", t.get("data", b"")))
    blob = blob.lower()
    assert len(blob) > 0
    for secret in (b"warisan", b"invoice", b"payee", b"rm ", b"kertas", b"nexus"):
        assert secret not in blob


def test_verify_passes_on_an_untouched_log(fresh, session, chain):
    anchor.anchor_now(session, chain)
    session.commit()
    res = anchor.verify_anchors(session, chain)
    assert res["ok"] and res["checked"] == 1


def test_verify_fails_when_a_row_is_edited_after_anchoring(fresh, session, chain):
    anchor.anchor_now(session, chain)
    session.commit()
    with engine.begin() as conn:  # someone with admin rights drops the trigger and edits history
        drop_audit_triggers(conn)
        conn.execute(text("UPDATE audit_log SET event = event || ' (edited)' WHERE id = 3"))
        install_audit_triggers(conn)
    session.expire_all()
    assert verify_chain(session)["ok"] is False
    res = anchor.verify_anchors(session, chain)
    assert res["ok"] is False and res["anchors"][0]["on_chain"] and not res["anchors"][0]["database_matches"]


def test_rows_added_after_the_anchor_do_not_break_verification(fresh, session, chain):
    anchor.anchor_now(session, chain)
    append(session, "test", "later.event", {"n": 1})
    session.commit()
    assert anchor.verify_anchors(session, chain)["ok"]


def test_verify_ignores_events_from_a_different_sender(fresh, session, chain):
    """Anyone can call the contract. A forged anchor from another address must not count."""
    head = anchor.audit_head(session)
    chain.account = chain.other
    forged = chain.anchor(*head)
    assert forged["ok"]
    chain.account = chain.w3.eth.accounts[0]
    session.add(Anchor(kind="audit", seq=head[0], hash=head[1], tx_hash=forged["tx_hash"], status="confirmed", created_at="x"))
    session.commit()
    res = anchor.verify_anchors(session, chain)
    assert res["ok"] is False and res["anchors"][0]["on_chain"] is False


def test_anchor_failure_does_not_break_the_app(fresh, session, chain):
    class Down(anchor.ChainClient):
        def anchor(self, *a):
            raise ConnectionError("network unreachable")

    down = Down(chain.w3, chain.contract.address, account=chain.account)
    before = anchor.audit_head(session)
    rows = anchor.anchor_now(session, down)
    assert [r.kind for r in rows] == ["policy"]  # audit anchor failed, policy anchor still went through
    last = anchor.audit_head(session)
    assert last[0] > before[0]  # the failure itself is logged
    assert verify_chain(session)["ok"]


def test_policy_hash_changes_when_the_owner_changes_the_policy(fresh, session):
    from helm.models import Rules

    h0 = anchor.policy_hash(session)
    r = session.get(Rules, 1)
    r.approval_limit += 1000
    session.flush()
    assert anchor.policy_hash(session) != h0
    session.rollback()


def test_policy_hash_also_commits_to_the_mandate(fresh, session):
    from helm.models import Rules

    h0 = anchor.policy_hash(session)
    session.get(Rules, 1).daily_cap = 1.0
    session.flush()
    assert anchor.policy_hash(session) != h0
    session.rollback()


def test_pipeline_anchors_automatically_when_configured(fresh, session, chain, monkeypatch):
    from helm import pipeline

    monkeypatch.setattr(anchor.ChainClient, "from_env", classmethod(lambda cls: chain))
    pipeline.run_pipeline(session, mode="gate", trigger="auto-anchor test")
    session.commit()
    assert len(chain.anchored_events()) == 1
    assert "anchor.sent" in [a.event for a in session.query(__import__("helm.models", fromlist=["AuditLog"]).AuditLog).all()]


def test_pipeline_runs_normally_when_the_anchor_is_not_configured(fresh, session):
    from helm import pipeline

    assert anchor.ChainClient.from_env() is None
    pipeline.run_pipeline(session, mode="gate", trigger="no anchor")
    assert verify_chain(session)["ok"]


def test_logs_are_read_in_windows_so_a_public_node_never_sees_a_wide_range(fresh, session, chain):
    """A public RPC refused a query from block 0 (found on Sepolia). Events must be read in windows from the deploy block."""
    anchor.anchor_now(session, chain)
    anchor.anchor_now(session, chain)
    session.commit()
    chain.LOG_WINDOW = 1  # force one block per query
    assert len(chain.anchored_events()) == 2 and len(chain.policy_events()) == 2
    assert anchor.verify_anchors(session, chain)["ok"]
