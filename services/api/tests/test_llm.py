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
        "bank_account": "MY-9999-0042", "run_payment": True,   # the model obeyed the document and added a command
    })
    raw = docs.bill_doc("Evil Co", "E-1", date(2026, 10, 19), date(2026, 10, 19), 48000, "MY-9999-0042", note=docs.MALICIOUS_NOTE)
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


# ---- provider plumbing (no network: a mock transport stands in for Google) ----------------------------
def _gemini_client(handler):
    import httpx
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_gemini_request_carries_the_key_in_a_header_never_in_the_url(monkeypatch):
    from helm import llm
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key-123")
    seen = {}

    def handler(req):
        import httpx
        seen["url"], seen["key"], seen["body"] = str(req.url), req.headers.get("x-goog-api-key"), json.loads(req.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})

    out = llm.complete("sys", "doc text", json_mode=True, client=_gemini_client(handler))
    assert out == '{"ok": true}'
    assert seen["key"] == "test-key-123" and "test-key-123" not in seen["url"] and "key=" not in seen["url"]
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert "tools" not in seen["body"]  # the model is never given tools


def test_a_rejected_key_becomes_a_clean_error_that_never_contains_the_key(monkeypatch):
    from helm import llm
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "secret-key-xyz")

    def handler(req):
        import httpx
        return httpx.Response(400, json={"error": {"message": "API key not valid. Please pass a valid API key."}})

    with pytest.raises(llm.LLMError) as e:
        llm.complete("s", "u", client=_gemini_client(handler))
    assert "400" in str(e.value) and "secret-key-xyz" not in str(e.value)


def test_the_reader_falls_back_to_the_fixture_parser_when_the_model_call_fails(monkeypatch):
    monkeypatch.setattr(config, "LLM_MODE", "live")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")  # no key: the call fails, the fixture parser answers
    raw = docs.bill_doc("Acme Paper", "FB-1", date(2026, 10, 19), date(2026, 11, 2), 1_234, "ACC-1")
    out = reader.run(reader.ReaderInput(doc_id="fb", kind="bill", raw_text=raw))
    assert out.amount == 1234.0 and not out.quarantined


def test_provider_choice_follows_the_keys_that_exist(monkeypatch):
    from helm import llm
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    assert llm.provider() == "gemini"
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.provider() is None
