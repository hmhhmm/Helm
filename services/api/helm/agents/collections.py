"""Collections Agent (2). Reads facts incl. pay history, plans chasers.

Ranks customers by their effect on the cash low point, not by age alone: for each customer it asks
"if a reminder brought this customer's payment forward by CHASE_DAYS, how much higher is the worst-case
low point?" using the same random draws, so the difference is the customer's own effect.
"""
from dataclasses import dataclass, replace
from datetime import date

import numpy as np

from helm.fmt import fdate, rm
from helm.forecast.montecarlo import ForecastInput, forecast

name = "collections"
CHASE_DAYS = 10  # assumption, shown to the owner
MIN_INVOICE = 1500.0


@dataclass
class OpenInvoice:
    id: str
    number: str
    amount: float
    due: date
    expected: date | None


@dataclass
class CustomerView:
    id: str
    name: str
    tone: str
    avg_delay: float
    open: list[OpenInvoice]


@dataclass
class CollectionsIn:
    facts: ForecastInput
    customers: list[CustomerView]
    unmanaged_commit_fn: object  # callable(ForecastResult) -> np.ndarray
    today: date
    min_balance: float


@dataclass
class ChaseOut:
    customer_id: str
    rank: int
    effect_rm: float
    chance_gain: float
    amount_open: float
    invoice_ids: list[str]
    tone: str
    why: str
    draft_en: str
    draft_ms: str


@dataclass
class CollectionsOut:
    ideas: list[ChaseOut]


def _low(res, commit) -> float:
    return float(res.scen.bands(commit)["p10"][1:].min())


def draft(c: CustomerView, today: date) -> tuple[str, str]:
    invs = sorted(c.open, key=lambda i: i.due)
    lines_en = "\n".join(f"- {i.number}: {rm(i.amount)}, due {fdate(i.due)}" + (f" ({(today - i.due).days} days overdue)" if i.due < today else "") for i in invs)
    lines_ms = "\n".join(f"- {i.number}: {rm(i.amount)}, matang {fdate(i.due, 'ms')}" + (f" (lewat {(today - i.due).days} hari)" if i.due < today else "") for i in invs)
    total = rm(sum(i.amount for i in invs))
    if c.tone == "firm":
        en = (f"Dear {c.name} accounts team,\n\nOur records show the following invoices are unpaid:\n{lines_en}\n\n"
              f"Total {total}. Please arrange payment this week, or tell us the date we can expect it.\n\nWarisan Printing Sdn Bhd (demo)")
        ms = (f"Kepada pasukan akaun {c.name},\n\nRekod kami menunjukkan invois berikut belum dibayar:\n{lines_ms}\n\n"
              f"Jumlah {total}. Sila uruskan bayaran minggu ini, atau maklumkan tarikh bayaran dijangka.\n\nWarisan Printing Sdn Bhd (demo)")
    else:
        en = (f"Hi {c.name} team,\n\nA friendly reminder about these invoices:\n{lines_en}\n\n"
              f"Total {total}. Could you let us know when we can expect payment? Thank you!\n\nWarisan Printing Sdn Bhd (demo)")
        ms = (f"Hai pasukan {c.name},\n\nPeringatan mesra tentang invois ini:\n{lines_ms}\n\n"
              f"Jumlah {total}. Boleh maklumkan bila kami boleh jangka bayaran? Terima kasih!\n\nWarisan Printing Sdn Bhd (demo)")
    return en, ms


def run(inp: CollectionsIn) -> CollectionsOut:
    small = replace(inp.facts, n_paths=400)
    base = forecast(small)
    commit = inp.unmanaged_commit_fn(base)
    base_low = _low(base, commit)
    base_p = base.scen.p_ok(commit, inp.min_balance)
    scored: list[ChaseOut] = []
    for c in inp.customers:
        total = sum(i.amount for i in c.open)
        if not c.open or total < MIN_INVOICE:
            continue
        what_if = replace(small, extra_delay={**small.extra_delay, c.id: small.extra_delay.get(c.id, 0) - CHASE_DAYS})
        res = forecast(what_if)
        low = _low(res, inp.unmanaged_commit_fn(res))
        p = res.scen.p_ok(inp.unmanaged_commit_fn(res), inp.min_balance)
        effect = min(max(0.0, low - base_low), total)  # one invoice cannot lift the low point by more than it is worth
        biggest = max(c.open, key=lambda i: i.amount)
        when = fdate(biggest.expected) if biggest.expected else "after the 90-day window"
        why = (f"{c.name} owes {rm(total)}; the biggest invoice ({rm(biggest.amount)}) is expected around {when}. "
               f"If a reminder brings payment {CHASE_DAYS} days sooner, your bad-case low point rises by about {rm(effect)}.")
        en, ms = draft(c, inp.today)
        scored.append(ChaseOut(c.id, 0, round(effect), round(p - base_p, 3), total, [i.id for i in c.open], c.tone, why, en, ms))
    scored.sort(key=lambda s: (-s.effect_rm, -s.amount_open, s.customer_id))
    for n, s in enumerate(scored, 1):
        s.rank = n
    return CollectionsOut(scored)
