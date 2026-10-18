"""Forecaster (1): Monte Carlo over invoice-payment and bill-timing distributions learned from history.

Pure numpy, no database. The service layer (helm.forecast.service) turns facts into a ForecastInput.
Behind the `Forecaster` interface so a GBM or time-series model can replace it later.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np


@dataclass(frozen=True)
class InvF:
    id: str
    customer_id: str
    amount: float
    issued: date
    due: date
    paid_on: date | None = None
    late_signal_days: int = 0


@dataclass(frozen=True)
class BillF:
    id: str
    kind: str  # supplier | payroll | statutory
    supplier_id: str | None
    payee: str
    amount: float
    issued: date
    due: date
    paid_on: date | None = None


@dataclass
class ForecastInput:
    today: date
    horizon: int
    start_balance: float
    invoices: list[InvF]
    bills: list[BillF]
    customer_terms: dict[str, int]
    supplier_terms: dict[str, int]
    n_paths: int = 1000
    seed: int = 2026
    extra_delay: dict[str, int] = field(default_factory=dict)  # what-if: customer pays N days later
    skip_bills: frozenset[str] = frozenset()  # what-if: pretend these bills do not exist
    include_projection: bool = True


@dataclass
class Cand:
    """A supplier bill the Policy Engine gets to gate."""
    bill_id: str
    amount: float
    due_idx: int  # day index of the due date, clamped to >= 0 (overdue bills are due 'today')


class ScenarioSet:
    """cumbase[n, t] = cumulative cash flow (receipts - fixed outflows - projected bills) by day t."""

    def __init__(self, today: date, horizon: int, start: float, cumbase: np.ndarray):
        self.today = today
        self.horizon = horizon
        self.start = start
        self.cumbase = cumbase  # shape (N, H+1), float64

    @property
    def n(self) -> int:
        return self.cumbase.shape[0]

    def day(self, idx: int) -> date:
        return self.today + timedelta(days=int(idx))

    def paths(self, committed_cum: np.ndarray | None = None) -> np.ndarray:
        if committed_cum is None:
            return self.start + self.cumbase
        return self.start + self.cumbase - committed_cum[None, :]

    def p_ok(self, committed_cum: np.ndarray, min_balance: float, rows: slice | None = None) -> float:
        """P(min over t<=H of balance_t >= B | the committed outflows)."""
        cb = self.cumbase if rows is None else self.cumbase[rows]
        lowest = (cb - committed_cum[None, :]).min(axis=1) + self.start
        return float((lowest >= min_balance).mean())

    def bands(self, committed_cum: np.ndarray | None = None) -> dict[str, np.ndarray]:
        p = self.paths(committed_cum)
        q = np.percentile(p, [10, 25, 50, 75, 90], axis=0)
        return {"p10": q[0], "p25": q[1], "p50": q[2], "p75": q[3], "p90": q[4]}

    def earliest_safe_idx(self, committed_cum: np.ndarray, amount: float, start_idx: int, min_balance: float, required: float) -> int | None:
        """Paying later is never less safe, so a binary search finds the earliest safe day.
        Returns None if even the last day of the horizon is not safe."""
        H = self.horizon

        def ok(idx: int) -> bool:
            add = np.zeros(H + 1)
            add[idx:] = amount
            return self.p_ok(committed_cum + add, min_balance) >= required

        if ok(start_idx):
            return start_idx
        if not ok(H):
            return None
        lo, hi = start_idx, H  # lo not ok, hi ok
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ok(mid):
                hi = mid
            else:
                lo = mid
        return hi


@dataclass
class ForecastResult:
    scen: ScenarioSet
    candidates: list[Cand]
    invoice_expect: dict[str, dict]  # id -> {median, p10, p90} as dates (None beyond horizon)
    assumptions: dict
    fixed_out: np.ndarray  # deterministic fixed outflows per day (payroll + statutory)
    projected_bills_mean: np.ndarray
    projected_receipts_mean: np.ndarray

    def unmanaged_commit(self) -> np.ndarray:
        """Every open supplier bill paid on its due date."""
        out = np.zeros(self.scen.horizon + 1)
        for c in self.candidates:
            out[c.due_idx:] += c.amount
        return out


class Forecaster:
    name = "forecaster"

    def run(self, inp: ForecastInput) -> ForecastResult:
        return forecast(inp)


def _learn(inp: ForecastInput):
    lo = inp.today - timedelta(days=365)
    per: dict[str, list[int]] = {}
    allv: list[int] = []
    gaps: dict[str, list[int]] = {}
    amounts: dict[str, list[float]] = {}
    issued_by: dict[str, list[date]] = {}
    for i in inp.invoices:
        issued_by.setdefault(i.customer_id, []).append(i.issued)
        amounts.setdefault(i.customer_id, []).append(i.amount)
        if i.paid_on and i.paid_on >= lo:
            d = (i.paid_on - i.due).days
            per.setdefault(i.customer_id, []).append(d)
            allv.append(d)
    portfolio = np.array(allv if allv else [0], dtype=float)
    return per, portfolio, issued_by, amounts


def forecast(inp: ForecastInput) -> ForecastResult:
    H, N = inp.horizon, inp.n_paths
    r = np.random.default_rng([inp.seed, inp.today.toordinal()])
    per, portfolio, issued_by, amounts = _learn(inp)

    flow = np.zeros((N, H + 1))
    rows_all: list[np.ndarray] = []
    cols_all: list[np.ndarray] = []
    vals_all: list[np.ndarray] = []

    def add_receipt(idx: np.ndarray, amount) -> None:
        keep = (idx >= 1) & (idx <= H)
        n = np.nonzero(keep)[0]
        rows_all.append(n)
        cols_all.append(idx[keep])
        vals_all.append(np.broadcast_to(amount, idx.shape)[keep] if np.ndim(amount) else np.full(n.shape, amount))

    def sample_delay(cust: str, signal: float, z: np.ndarray, u: np.ndarray, pick_own: np.ndarray, pick_port: np.ndarray) -> np.ndarray:
        own = np.array(per.get(cust, []), dtype=float)
        w = len(own) / (len(own) + 2.0)
        base = np.where(
            (u < w) & (len(own) > 0),
            own[pick_own % max(len(own), 1)] if len(own) else 0.0,
            portfolio[pick_port % len(portfolio)],
        )
        d = base + z * 1.5
        if signal:
            d = d + signal + z * 0.4 * abs(signal)  # shifted AND wider: what the owner knows is uncertain
        return np.rint(d).astype(int)

    expect: dict[str, dict] = {}
    # --- open invoices: known amounts, uncertain payment day -----------------
    for inv in inp.invoices:
        if inv.paid_on is not None:
            continue
        z = r.standard_normal(N); u = r.random(N)
        po = r.integers(0, 1_000_000, N); pp = r.integers(0, 1_000_000, N)
        sig = inv.late_signal_days + inp.extra_delay.get(inv.customer_id, 0)
        delay = sample_delay(inv.customer_id, sig, z, u, po, pp)
        idx = (inv.due - inp.today).days + delay
        stuck = idx <= 0  # already past its sampled day and still unpaid: pays soon, but not today
        idx = np.where(stuck, 1 + np.floor(r.exponential(8.0, N)).astype(int), idx)
        add_receipt(idx, inv.amount)
        med = int(np.median(idx))
        expect[inv.id] = {
            "median": inp.today + timedelta(days=med) if med <= H else None,
            "p10": inp.today + timedelta(days=int(np.percentile(idx, 10))),
            "p90": inp.today + timedelta(days=int(np.percentile(idx, 90))),
        }

    # --- projected future invoices (not yet issued) --------------------------
    proj_receipts_mean = np.zeros(H + 1)
    if inp.include_projection:
        for cust, dates in issued_by.items():
            ds = sorted(dates)
            if len(ds) < 3:
                continue
            gap = float(np.median(np.diff([d.toordinal() for d in ds])))
            logs = np.log(np.array(amounts[cust]))
            mu, sd = float(logs.mean()), float(max(logs.std(), 0.05))
            nxt = ds[-1].toordinal() + gap
            terms = inp.customer_terms.get(cust, 30)
            while nxt <= inp.today.toordinal() + H:
                t_issue = int(round(max(nxt, inp.today.toordinal() + 1)))
                z = r.standard_normal(N); u = r.random(N)
                po = r.integers(0, 1_000_000, N); pp = r.integers(0, 1_000_000, N)
                sig = inp.extra_delay.get(cust, 0)
                issue = t_issue + np.rint(r.normal(0, 0.12 * gap, N)).astype(int)
                issue = np.maximum(issue, inp.today.toordinal() + 1)
                amt = np.exp(r.normal(mu, sd, N))
                idx = issue + terms + sample_delay(cust, sig, z, u, po, pp) - inp.today.toordinal()
                add_receipt(idx, amt)
                ok = (idx >= 1) & (idx <= H)
                np.add.at(proj_receipts_mean, idx[ok], amt[ok] / N)
                nxt += gap

    # --- fixed outflows: payroll and statutory (known calendar) --------------
    fixed_out = np.zeros(H + 1)
    cands: list[Cand] = []
    for b in inp.bills:
        if b.paid_on is not None or b.id in inp.skip_bills:
            continue
        idx = (b.due - inp.today).days
        if b.kind != "supplier":
            if idx <= H:
                fixed_out[max(idx, 0):] += b.amount  # cumulative-from-day form, converted below
            continue
        if idx <= H:
            cands.append(Cand(b.id, b.amount, max(idx, 0)))
    # fixed_out above is cumulative (step) form; keep as cumulative array.

    # --- projected supplier bills (not yet received): background outflows ----
    proj_bills_mean = np.zeros(H + 1)
    proj_cum = np.zeros((N, H + 1))
    if inp.include_projection:
        by_sup: dict[str, list[BillF]] = {}
        for b in inp.bills:
            if b.kind == "supplier" and b.supplier_id:
                by_sup.setdefault(b.supplier_id, []).append(b)
        for sid, bs in by_sup.items():
            if len(bs) < 3:
                continue
            bs = sorted(bs, key=lambda x: x.issued)
            gap = float(np.median(np.diff([x.issued.toordinal() for x in bs])))
            logs = np.log(np.array([x.amount for x in bs]))
            mu, sd = float(logs.mean()), float(logs.std())
            terms = inp.supplier_terms.get(sid, 30)
            nxt = bs[-1].issued.toordinal() + gap
            while nxt <= inp.today.toordinal() + H:
                if nxt > inp.today.toordinal():
                    due_idx = int(nxt + terms - inp.today.toordinal())
                    if 1 <= due_idx <= H:
                        amt = np.exp(r.normal(mu, sd, N)) if sd > 0 else np.full(N, np.exp(mu))
                        proj_cum[:, due_idx:] += amt[:, None]
                        proj_bills_mean[due_idx] += amt.mean()
                nxt += gap

    for rows, cols, vals in zip(rows_all, cols_all, vals_all):
        np.add.at(flow, (rows, cols), vals)
    cumbase = np.cumsum(flow, axis=1) - fixed_out[None, :] - proj_cum

    scen = ScenarioSet(inp.today, H, inp.start_balance, cumbase)
    n_paid = sum(1 for i in inp.invoices if i.paid_on)
    assumptions = {
        "paths": N,
        "history_invoices_used": int(len(portfolio)) if n_paid else 0,
        "customers_learned": len(per),
        "method": "Monte Carlo: each open invoice is paid after its customer's own past delays (blended with all customers when history is thin); new invoices and bills are projected from each customer's and supplier's usual rhythm.",
        "projection": inp.include_projection,
    }
    return ForecastResult(
        scen=scen, candidates=sorted(cands, key=lambda c: (c.due_idx, c.bill_id)), invoice_expect=expect,
        assumptions=assumptions, fixed_out=fixed_out, projected_bills_mean=proj_bills_mean,
        projected_receipts_mean=proj_receipts_mean,
    )
