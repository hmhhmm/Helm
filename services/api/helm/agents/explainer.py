"""Explainer Agent (5). Reads receipts and the audit log; writes plain-language reasons.

Fixture mode is a deterministic template. LLM_MODE=live may re-word it, but never changes a number.
"""
from dataclasses import dataclass
from datetime import date

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
