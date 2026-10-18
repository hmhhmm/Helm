"""Agents get a frozen, read-only view of the owner's rules. They cannot write rules."""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from helm.models import Rules, SimState


@dataclass(frozen=True)
class RulesView:
    min_balance: float
    risk_tolerance: float  # alpha: accepted chance of dropping below the minimum
    approval_limit: float
    protected_payees: tuple[str, ...]
    kill_switch: bool
    horizon_days: int

    @property
    def required_confidence(self) -> float:
        return round(1.0 - self.risk_tolerance, 4)


def load_rules(session: Session) -> RulesView:
    r = session.get(Rules, 1)
    return RulesView(
        min_balance=r.min_balance,
        risk_tolerance=r.risk_tolerance,
        approval_limit=r.approval_limit,
        protected_payees=tuple(r.protected_payees or ()),
        kill_switch=r.kill_switch,
        horizon_days=r.horizon_days,
    )


def sim_today(session: Session) -> date:
    return session.get(SimState, 1).today
