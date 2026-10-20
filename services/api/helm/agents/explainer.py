"""Explainer Agent (5). Reads receipts and the audit log; writes plain-language reasons.

Fixture mode is a deterministic template. LLM_MODE=live may re-word it, but never changes a number.
"""
import re
from dataclasses import dataclass
from datetime import date

from helm import config

from helm.fmt import fdate, rm

name = "explainer"


@dataclass
class ExplainerIn:
    payee: str
    amount: float
    paid_on: date
    due: date
    decision_why: str
    verdict_history: list[str]  # e.g. ["HOLD", "ALLOW"]


@dataclass
class ExplainerOut:
    text: str


def run(inp: ExplainerIn) -> ExplainerOut:
    held = "HOLD" in inp.verdict_history
    late = (inp.paid_on - inp.due).days
    timing = (
        "on its due date" if late == 0
        else f"{late} days after its due date" if late > 0
        else f"{-late} days before its due date"
    )
    lead = f"Paid {inp.payee} {rm(inp.amount)} on {fdate(inp.paid_on)}, {timing}."
    why = ("It was held first because paying earlier risked dropping under your minimum; it was released once the forecast said it was safe. "
           if held else "")
    return ExplainerOut(f"{lead} {why}{inp.decision_why}")


_NUM = re.compile(r"\d[\d,]*\.?\d*")


def numbers_preserved(original: str, reworded: str) -> bool:
    """A model may change the wording but never a number or a date."""
    return sorted(_NUM.findall(original)) == sorted(_NUM.findall(reworded))


def _live_reword(text: str) -> str | None:
    from helm import llm

    try:
        return llm.complete(
            "Rewrite this payment explanation in plain, friendly English. Keep every number and date exactly as written. Reply with the rewritten text only.",
            text,
        )
    except Exception:
        return None


def run_with_model(inp: ExplainerIn) -> ExplainerOut:
    """Fixture text first; with LLM_MODE=live the model may re-word it, and the result is used only if no number changed."""
    base = run(inp)
    if config.LLM_MODE != "live":
        return base
    reworded = _live_reword(base.text)
    return ExplainerOut(reworded) if reworded and numbers_preserved(base.text, reworded) else base
