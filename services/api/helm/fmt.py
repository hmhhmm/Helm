"""Plain-language formatting shared by the engine and the PDF brief."""
from datetime import date

MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_MS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogos", "Sep", "Okt", "Nov", "Dis"]


def rm(x: float) -> str:
    v = f"{abs(round(x)):,}"
    return f"(RM {v})" if x < 0 else f"RM {v}"


def fdate(d: date | None, lang: str = "en") -> str:
    if d is None:
        return "-"
    return f"{d.day} {(MONTHS_MS if lang == 'ms' else MONTHS_EN)[d.month - 1]}"


def pct(p: float) -> str:
    return f"{round(p * 100)}%"
