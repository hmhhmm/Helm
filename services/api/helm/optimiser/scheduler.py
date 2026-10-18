"""Scheduler optimiser (OR-Tools CP-SAT) for the bill-release schedule.

Chooses a release day for every open supplier bill. Statutory and payroll items are fixed inside the
scenario matrix and are never moved. Objective: pay as close to the due date as possible
(weighted lateness) subject to the chance constraint, using the scenario approach:

    for scenarios s = 1..S and days t:  start + cum_s(t) - paid(t) >= B   unless z_s = 1
    sum_s z_s <= floor(alpha * S)
"""
from dataclasses import dataclass

import numpy as np
from ortools.sat.python import cp_model

from helm.forecast.montecarlo import Cand, ScenarioSet

MAX_LATE_DAYS = 30  # suppliers are not stretched further than a month by the optimiser
LATE_FLAT_PENALTY = 10  # 'maximise on-time payments': being late at all costs extra
BEYOND_PENALTY = 400  # pushed past the horizon: only when delays alone cannot protect the minimum


@dataclass
class PlanItem:
    bill_id: str
    due_idx: int
    plan_idx: int | None  # None = beyond the horizon
    days_late: int


@dataclass
class PlanResult:
    items: dict[str, PlanItem]
    status: str  # optimal | feasible | relaxed
    scenarios: int


def plan_releases(
    cands: list[Cand], scen: ScenarioSet, min_balance: float, alpha: float,
    weights: dict[str, int] | None = None, scenarios: int = 160, time_limit: float = 5.0,
) -> PlanResult:
    H = scen.horizon
    weights = weights or {}
    if not cands:
        return PlanResult({}, "optimal", 0)
    S = min(scenarios, scen.n)
    X = scen.cumbase[:S] + scen.start  # (S, H+1)
    amounts = {c.bill_id: int(round(c.amount)) for c in cands}
    total = sum(amounts.values())

    m = cp_model.CpModel()
    x: dict[tuple[str, int], cp_model.IntVar] = {}
    window: dict[str, list[int]] = {}
    SENT = H + 1  # "beyond the horizon"
    for c in cands:
        days = list(range(c.due_idx, min(H, c.due_idx + MAX_LATE_DAYS) + 1)) + [SENT]
        window[c.bill_id] = days
        vars_ = []
        for d in days:
            v = m.NewBoolVar(f"x_{c.bill_id}_{d}")
            x[(c.bill_id, d)] = v
            vars_.append(v)
        m.AddExactlyOne(vars_)

    def paid_by(t: int):
        terms = []
        for c in cands:
            for d in window[c.bill_id]:
                if d <= t:
                    terms.append(amounts[c.bill_id] * x[(c.bill_id, d)])
        return sum(terms) if terms else 0

    paid = [paid_by(t) for t in range(H + 1)]
    z = [m.NewBoolVar(f"z_{s}") for s in range(S)]
    big = total + 400_000
    for s in range(S):
        for t in range(H + 1):
            rhs = int(np.floor(X[s, t] - min_balance))
            if rhs >= total:
                continue  # can never bind
            m.Add(paid[t] <= rhs + big * z[s])
    m.Add(sum(z) <= int(np.floor(alpha * S)))

    obj = []
    for c in cands:
        # Bills due soon are the ones suppliers expect imminently, so they cost more to delay than bills
        # still weeks out (which may also resolve themselves before they fall due).
        w = (1 + 60 // (7 + c.due_idx)) * weights.get(c.bill_id, 1)
        for d in window[c.bill_id]:
            if d == SENT:
                cost = BEYOND_PENALTY
            else:
                late = d - c.due_idx
                # relationship cost grows faster than linearly: many short delays beat one long one
                cost = (LATE_FLAT_PENALTY + late + late * late // 8) if late > 0 else 0
            obj.append(w * cost * x[(c.bill_id, d)])
    m.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 4
    solver.parameters.random_seed = 2026
    status = solver.Solve(m)

    items: dict[str, PlanItem] = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for c in cands:
            d = next(dd for dd in window[c.bill_id] if solver.Value(x[(c.bill_id, dd)]))
            items[c.bill_id] = PlanItem(c.bill_id, c.due_idx, None if d == SENT else d, (MAX_LATE_DAYS if d == SENT else d - c.due_idx))
        return PlanResult(items, "optimal" if status == cp_model.OPTIMAL else "feasible", S)
    # Cash is tight even if nothing optional were paid: fall back to due dates and let the Policy Engine gate.
    for c in cands:
        items[c.bill_id] = PlanItem(c.bill_id, c.due_idx, c.due_idx, 0)
    return PlanResult(items, "relaxed", S)
