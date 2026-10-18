"""Scheduler Agent (3). Reads the cash range, picks which bills to pay and when (CP-SAT)."""
from dataclasses import dataclass

from helm.forecast.montecarlo import Cand, ScenarioSet
from helm.optimiser.scheduler import PlanResult, plan_releases

name = "scheduler"


@dataclass
class SchedulerIn:
    candidates: list[Cand]
    scen: ScenarioSet
    min_balance: float
    risk_tolerance: float
    weights: dict[str, int]  # protected payees weigh more


@dataclass
class SchedulerOut:
    plan: PlanResult


def run(inp: SchedulerIn) -> SchedulerOut:
    return SchedulerOut(plan_releases(inp.candidates, inp.scen, inp.min_balance, inp.risk_tolerance, inp.weights))
