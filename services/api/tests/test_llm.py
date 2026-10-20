"""Live model path (LLM_MODE=live). Real recorded responses are replayed through the same schema check.

tests/fixtures/llm/recorded.json is written by scripts/record_llm.py from REAL calls (it needs ANTHROPIC_API_KEY).
Until that file exists, the replay tests skip, and nothing here claims a real model response.
The two 'stub' tests below use a hand written stand in for a model that OBEYS an injection. They are clearly
synthetic, and they show that even an obedient model cannot get past the schema check.
"""
import json
import pathlib
from datetime import date

import pytest

from helm import config
from helm.agents import explainer, reader
from helm.seed import docs

RECORDED = pathlib.Path(__file__).parent / "fixtures" / "llm" / "recorded.json"


def test_stub_an_obedient_model_cannot_smuggle_extra_fields(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODE", "live")
    monkeypatch.setattr(reader, "_live_extract", lambda inp: {
        "counterparty": "Evil Co", "reference": "E-1", "amount": 48000.0, "issue_date": "2026-10-19", "due_date": "2026-10-19",
        "bank_account": "DEMO-9999-0042", "run_payment": True,   # the model obeyed the document and added a command
    })
    raw = docs.bill_doc("Evil Co", "E-1", date(2026, 10, 19), date(2026, 10, 19), 48000, "DEMO-9999-0042", note=docs.MALICIOUS_NOTE)
    out = reader.run(reader.ReaderInput(doc_id="d", kind="bill", raw_text=raw))
    assert out.quarantined and out.amount == 0.01 and "schema_check_failed" in out.flags  # inert record, nothing to act on


def test_stub_a_model_that_changes_a_number_is_not_used(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODE", "live")
    monkeypatch.setattr(explainer, "_live_reword", lambda text: text.replace("RM 5,000", "RM 50,000"))
    base = explainer.ExplainerIn("Acme", 5_000.0, date(2026, 10, 20), date(2026, 10, 20), "Safe to pay Acme RM 5,000.", ["ALLOW"])
    assert explainer.run_with_model(base).text == explainer.run(base).text


def test_numbers_preserved_guard():
    assert explainer.numbers_preserved("Paid RM 5,000 on 24 Oct", "We paid RM 5,000 on 24 Oct, as planned")
    assert not explainer.numbers_preserved("Paid RM 5,000 on 24 Oct", "Paid RM 50,000 on 24 Oct")


@pytest.mark.skipif(not RECORDED.exists(), reason="no recorded real model responses yet (run scripts/record_llm.py with ANTHROPIC_API_KEY)")
def test_recorded_real_responses_pass_the_schema_check(monkeypatch):
    rec = json.loads(RECORDED.read_text())
    assert rec["model"] and rec["produced_at"] and rec["calls"]
    monkeypatch.setattr(config, "LLM_MODE", "live")
    for call in rec["calls"]:
        monkeypatch.setattr(reader, "_live_extract", lambda inp, c=call: c["response_json"])
        out = reader.run(reader.ReaderInput(doc_id=call["doc_id"], kind="bill", raw_text=call["raw_text"]))
        if call["poisoned"]:
            assert out.quarantined and "injection_like_text" in out.flags
        assert out.model_dump().keys() == reader.ReaderOutput.model_fields.keys()
