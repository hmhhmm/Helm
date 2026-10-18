"""Treasury Agent (4). Reads the bill plan; plans sweeps (park spare cash) and top-ups (cover a dip)."""
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil, floor

import numpy as np

from helm.config import RESERVE_APY
from helm.fmt import fdate, rm
from helm.forecast.montecarlo import ScenarioSet

name = "treasury"
BUFFER = 10_000.0  # comfort cushion above the minimum before cash counts as "spare"
MIN_SWEEP = 5_000.0
SWEEP_CAP = 30_000.0


@dataclass
class TreasuryIn:
    scen: ScenarioSet
    plan_commit: np.ndarray  # cumulative planned bill outflows (Scheduler's plan)
    unmanaged_commit: np.ndarray  # everything paid on its due date
    min_balance: float
    required_confidence: float
    operating: float
    reserve: float
    today: date


@dataclass
class TreasuryIdea:
    kind: str  # sweep | top_up
    amount: float
    on: date
    reason: str
    reason_ms: str
    interest_estimate: float | None = None
    covers_date: date | None = None


@dataclass
class TreasuryOut:
    ideas: list[TreasuryIdea]
    spare_estimate: float
    planned_low: float


def run(inp: TreasuryIn) -> TreasuryOut:
    B, H = inp.min_balance, inp.scen.horizon
    q = int(round((1 - inp.required_confidence) * 100))
    pq_plan = np.percentile(inp.scen.paths(inp.plan_commit), q, axis=0)
    pq_free = np.percentile(inp.scen.paths(inp.unmanaged_commit), q, axis=0)
    ideas: list[TreasuryIdea] = []

    spare = float(pq_plan.min() - (B + BUFFER))
    if spare >= MIN_SWEEP and inp.operating > B + BUFFER:
        amount = float(min(floor(spare / 1000) * 1000, SWEEP_CAP, inp.operating - B - BUFFER))
        if amount >= MIN_SWEEP:
            est = amount * RESERVE_APY * 30 / 365
            ideas.append(TreasuryIdea(
                "sweep", amount, inp.today,
                f"Even in a bad-but-plausible case (1 in {round(100 / max(q, 1))}) your balance stays {rm(spare)} above your comfort level for the next {H} days. Park {rm(amount)} in the reserve.",
                f"Walaupun dalam kes buruk tetapi munasabah, baki anda kekal {rm(spare)} melebihi tahap selesa selama {H} hari. Simpan {rm(amount)} dalam rizab.",
                round(est, 2),
            ))

    free_low = float(pq_free.min())
    if free_low < B:
        idx = int(np.argmin(pq_free))
        low_day = inp.scen.day(idx)
        need = ceil((B - free_low) / 1000) * 1000
        amount = float(min(need, floor(inp.reserve / 1000) * 1000))
        if amount >= 1000:
            on = max(inp.today, low_day - timedelta(days=5))
            full = amount >= need
            ideas.append(TreasuryIdea(
                "top_up", amount, on,
                (f"If you pay every bill on its due date, a bad-but-plausible case dips to {rm(free_low)} around {fdate(low_day)}. "
                 f"Moving {rm(amount)} from the reserve by {fdate(on)} " + ("would let Helm pay every bill on time." if full else "covers part of the gap; Helm will still hold some bills.")),
                (f"Jika semua bil dibayar pada tarikh matang, kes buruk tetapi munasabah jatuh ke {rm(free_low)} sekitar {fdate(low_day, 'ms')}. "
                 f"Memindahkan {rm(amount)} daripada rizab menjelang {fdate(on, 'ms')} " + ("membolehkan Helm membayar semua bil tepat pada masanya." if full else "menampung sebahagian jurang; Helm masih akan menahan beberapa bil.")),
                None, low_day,
            ))
    return TreasuryOut(ideas, max(spare, 0.0), float(pq_plan.min()))
