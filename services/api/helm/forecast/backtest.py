"""Forecast track record: re-forecast from past weekly snapshots and compare with what really happened.

Each snapshot only sees facts that were known on its day. Whatever the numbers turn out to be is what
is shown (on synthetic history); nothing is tuned to look good.
"""
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.forecast.montecarlo import forecast
from helm.forecast.service import build_input
from helm.models import Balance

_cache: dict = {}


def track_record(session: Session, today: date, weeks: int = 6, window: int = 28) -> dict:
    key = (today, weeks)
    if key in _cache:
        return _cache[key]
    actual = {b.on: b.amount for b in session.execute(select(Balance).where(Balance.account == "operating")).scalars()}
    rows = []
    inside = total = 0
    abs_err: list[float] = []
    for w in range(weeks, 0, -1):
        origin = today - timedelta(days=7 * w)
        if origin not in actual:
            continue
        inp = build_input(session, today, window, as_of=origin, n_paths=500)
        res = forecast(inp)
        un = res.unmanaged_commit()
        bands = res.scen.bands(un)
        n_in = n = 0
        errs = []
        for i in range(1, window + 1):
            d = origin + timedelta(days=i)
            if d > today or d not in actual:
                break
            n += 1
            n_in += int(bands["p10"][i] <= actual[d] <= bands["p90"][i])
            errs.append(abs(actual[d] - bands["p50"][i]))
        if n:
            rows.append({"origin": origin.isoformat(), "days_checked": n, "inside_80": round(n_in / n, 3),
                         "median_abs_error": round(float(np.median(errs)))})
            inside += n_in; total += n; abs_err += errs
    out = {
        "snapshots": rows, "days_checked": total, "coverage_80": round(inside / total, 3) if total else None,
        "median_abs_error": round(float(np.median(abs_err))) if abs_err else None,
        "stated_coverage": 0.8,
        "note": "Back-test on synthetic history. Each snapshot only used what was known on its day.",
    }
    _cache[key] = out
    return out
