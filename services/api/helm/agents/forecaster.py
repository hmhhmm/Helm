"""Forecaster Agent (1). Reads facts, predicts the next 90 days as a calibrated range."""
from dataclasses import dataclass

from helm.forecast.montecarlo import ForecastInput, ForecastResult, Forecaster

name = "forecaster"
_impl = Forecaster()


@dataclass
class ForecasterIn:
    facts: ForecastInput


@dataclass
class ForecasterOut:
    result: ForecastResult


def run(inp: ForecasterIn) -> ForecasterOut:
    return ForecasterOut(_impl.run(inp.facts))
