"""One small door to a language model. Used only by the Reader (extraction) and the Explainer (wording).

Providers: Gemini (REST, key in the x-goog-api-key header, never in the URL) or Anthropic. Every caller treats a failure
as "no answer" and falls back to the deterministic fixture path, and every answer still goes through the same schema
check or number guard, so a model can never act on its own.
"""
import os

import httpx

from helm import config

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(Exception):
    pass


def provider() -> str | None:
    if config.LLM_PROVIDER in ("gemini", "anthropic"):
        return config.LLM_PROVIDER
    if config.GEMINI_API_KEY:
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def model_name() -> str:
    return config.GEMINI_MODEL if provider() == "gemini" else config.LLM_MODEL


def complete(system: str, user: str, *, json_mode: bool = False, client: httpx.Client | None = None, timeout: float = 30.0) -> str:
    """Returns the model's text, or raises LLMError. The API key is never included in an error message."""
    p = provider()
    if p == "gemini":
        if not config.GEMINI_API_KEY:
            raise LLMError("GEMINI_API_KEY is not set")
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 600, **({"responseMimeType": "application/json"} if json_mode else {})},
        }
        try:
            c = client or httpx.Client(timeout=timeout)
            r = c.post(GEMINI_URL.format(model=config.GEMINI_MODEL), json=body, headers={"x-goog-api-key": config.GEMINI_API_KEY})
        except httpx.HTTPError as exc:
            raise LLMError(f"network error: {type(exc).__name__}") from None
        if r.status_code != 200:
            detail = ""
            try:
                detail = r.json().get("error", {}).get("message", "")[:160]
            except ValueError:
                pass
            raise LLMError(f"gemini HTTP {r.status_code}: {detail}")
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, ValueError):
            raise LLMError("gemini returned no text") from None
    if p == "anthropic":
        try:
            import anthropic  # type: ignore

            msg = anthropic.Anthropic().messages.create(model=config.LLM_MODEL, max_tokens=400, system=system, messages=[{"role": "user", "content": user}])
            return msg.content[0].text.strip()
        except Exception as exc:
            raise LLMError(f"anthropic error: {type(exc).__name__}") from None
    raise LLMError("no model provider is configured")
