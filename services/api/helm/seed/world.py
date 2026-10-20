"""Deterministic synthetic world for Warisan Printing Sdn Bhd (fictional). seed = 2026.

12 months of history, the open items as of TODAY, and 26 weeks of future arrivals that the
simulator releases as time advances. Nothing here is real data.
"""
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from helm.config import SEED

TODAY = date(2026, 10, 19)  # a Monday
HIST_START = date(2025, 10, 20)
SIM_END = TODAY + timedelta(weeks=26)
OPENING_TARGET = 85_000.0
RESERVE_START = 30_000.0
AMOUNT_SCALE = 1.04


@dataclass(frozen=True)
class CustomerSpec:
    id: str
    name: str
    terms: int
    delay_mu: float  # days paid after due date (negative = early)
    delay_sd: float
    per_year: int
    amt_mu: float
    amt_sigma: float = 0.25
    tone: str = "friendly"
    day_of_month: int | None = None  # fixed monthly billing day


CUSTOMERS = [
    CustomerSpec("c01", "Cahaya Mega Retail Sdn Bhd", 45, 17, 5, 12, 30_000, 0.12, day_of_month=22),
    CustomerSpec("c02", "Lim Bros Trading Sdn Bhd", 30, 4, 4, 10, 14_000, 0.20),
    CustomerSpec("c03", "Seri Murni Packaging Sdn Bhd", 30, 2, 4, 10, 7_200),
    CustomerSpec("c04", "Taman Jaya Stationery", 30, -1, 3, 10, 4_800),
    CustomerSpec("c05", "Orkid Events Management", 30, 5, 5, 9, 6_400),
    CustomerSpec("c06", "Nusa Print Agency", 30, 0, 3, 9, 5_600),
    CustomerSpec("c07", "Bayu Education Centre", 45, 3, 5, 8, 8_100),
    CustomerSpec("c08", "Delima Catering Sdn Bhd", 30, 6, 5, 8, 3_900),
    CustomerSpec("c09", "Harmoni Clinic Group", 30, 1, 3, 9, 5_300),
    CustomerSpec("c10", "Pelangi Kindergarten Chain", 30, 4, 4, 7, 6_800),
    CustomerSpec("c11", "Sri Kota Property Agents", 30, -2, 3, 7, 4_100),
    CustomerSpec("c12", "Mutiara Travel & Tours", 30, 30, 9, 7, 5_900, tone="firm"),
    CustomerSpec("c13", "Kedai Buku Sinar", 30, 24, 8, 6, 4_400, tone="firm"),
    CustomerSpec("c14", "Anggun Boutique Sdn Bhd", 30, 3, 4, 6, 3_200),
    CustomerSpec("c15", "Titiwangsa Law Chambers", 30, 0, 2, 6, 5_100),
    CustomerSpec("c16", "Bumi Hijau Organics", 30, 5, 4, 5, 4_600),
    CustomerSpec("c17", "Jasa Cekap Logistics", 45, 2, 4, 5, 7_400),
    CustomerSpec("c18", "Lestari Fitness Club", 30, 1, 3, 5, 3_700),
]


@dataclass(frozen=True)
class SupplierSpec:
    id: str
    name: str
    account: str
    issue_day: int
    every: int  # months between bills
    offset: int
    terms: int
    mean: float
    sd_frac: float = 0.08
    fixed: bool = False


SUPPLIERS = [
    SupplierSpec("s01", "Syarikat Kertas Sdn Bhd", "MY-4471-0001", 9, 1, 0, 45, 15_500),
    SupplierSpec("s02", "Tinta Utama Supplies", "MY-4471-0002", 10, 1, 0, 30, 7_000, 0.1),
    SupplierSpec("s03", "Plat & Film Enterprise", "MY-4471-0003", 14, 2, 0, 30, 7_600, 0.12),
    SupplierSpec("s04", "Mesin Servis Teknik", "MY-4471-0004", 6, 4, 1, 30, 6_200, 0.3),
    SupplierSpec("s05", "Kilang Kadbod Sdn Bhd", "MY-4471-0005", 18, 2, 0, 45, 9_500, 0.1),
    SupplierSpec("s06", "Pengangkutan Laju", "MY-4471-0006", 24, 2, 0, 30, 3_000, 0.15),
    SupplierSpec("s07", "Bekalan Elektrik Malaysia", "MY-4471-0007", 5, 1, 0, 21, 4_200, 0.1),
    SupplierSpec("s08", "Sewa Premis Klang", "MY-4471-0008", 20, 1, 0, 12, 7_000, 0.0, True),
    SupplierSpec("s09", "Pek Bungkus Mesra", "MY-4471-0009", 12, 2, 1, 45, 3_600, 0.12),
    SupplierSpec("s10", "Insurans Perniagaan Selamat", "MY-4471-0010", 8, 6, 2, 30, 4_200, 0.0, True),
    SupplierSpec("s11", "Telekom Bersama", "MY-4471-0011", 3, 2, 0, 30, 1_050, 0.05),
    SupplierSpec("s12", "Kimia Cuci Pantas", "MY-4471-0012", 22, 2, 0, 30, 2_200, 0.15),
]

# Statutory payees (registry entries, not counted among the 12 suppliers).
STATUTORY = [
    ("g01", "EPF (statutory)", "GOV-EPF", "statutory"),
    ("g02", "SOCSO (statutory)", "GOV-SOCSO", "statutory"),
    ("g03", "EIS (statutory)", "GOV-EIS", "statutory"),
    ("g04", "LHDN PCB (statutory)", "GOV-PCB", "statutory"),
    ("g05", "SST (statutory)", "GOV-SST", "statutory"),
    ("g06", "Warisan payroll run", "PAYROLL-01", "payroll"),
]

PAYROLL = 41_500.0
EPF, SOCSO, EIS, PCB, SST = 5_420.0, 880.0, 176.0, 1_640.0, 3_250.0

# Hand-placed so the story lands (see DECISIONS.md): (supplier_id, issue year, month) -> amount
BILL_OVERRIDES: dict[tuple[str, int, int], float] = {
    ("s01", 2026, 10): 18_400.0,  # the RM 18,400 paper bill, due late Nov
    ("s04", 2026, 10): 12_000.0,  # annual press overhaul
    ("s05", 2026, 9): 13_500.0,   # bulk board order ahead of the year-end rush
}
ISSUE_OVERRIDES: dict[tuple[str, int, int], date] = {
    ("s04", 2026, 10): date(2026, 10, 16),
}

# The story: Sep-Oct billing was soft (school holidays), so receipts due in November are small ...
SOFT_FROM, SOFT_TO, SOFT_FACTOR = date(2026, 9, 15), date(2026, 10, 19), 0.3
# ... and the one big receipt is a 62-day payer's year-end order that only lands in December.
EXTRA_INVOICES = [("c01", date(2026, 9, 28), 52_000.0), ("c07", date(2026, 10, 17), 44_000.0)]


def rng() -> np.random.Generator:
    return np.random.default_rng(SEED)


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def month_end(d: date) -> date:
    return add_months(d, 1) - timedelta(days=1)


def round10(x: float) -> float:
    return float(int(round(x / 10.0)) * 10)
