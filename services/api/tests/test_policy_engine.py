"""Policy Engine: every rule and every verdict (ALLOW, HOLD, ESCALATE, DENY)."""
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from helm.engine.policy import Payee, PolicyContext, ProposalIn, Receipt, decide, evaluate_all
from helm.forecast.montecarlo import ScenarioSet
from helm.rules_view import RulesView

TODAY = date(2026, 10, 19)
H = 90


def scen(level: float = 60_000, dip_day: int | None = None, dip: float = 0.0, n: int = 400) -> ScenarioSet:
    """Flat cash flow, optionally with a one-off outflow at dip_day that is recovered 10 days later."""
    cum = np.zeros((n, H + 1))
    rng = np.random.default_rng(1)
    if dip_day is not None:
        noise = rng.normal(0, 1500, n)
        for t in range(dip_day, min(H + 1, dip_day + 10)):
            cum[:, t] -= dip + noise
    return ScenarioSet(TODAY, H, level, cum)


def rules(**kw) -> RulesView:
    base = dict(min_balance=20_000, risk_tolerance=0.10, approval_limit=25_000, protected_payees=("Protected Co",), kill_switch=False, horizon_days=H)
    base.update(kw)
    return RulesView(**base)


REGISTRY = {
    "Acme Paper": Payee("Acme Paper", "ACC-1", "supplier", 8_000),
    "Protected Co": Payee("Protected Co", "ACC-2", "supplier", 5_000),
    "EPF (statutory)": Payee("EPF (statutory)", "GOV-EPF", "statutory"),
}


def ctx(s=None, r=None, **kw) -> PolicyContext:
    return PolicyContext(rules=r or rules(), today=TODAY, scen=s or scen(), registry=REGISTRY, **kw)


def bill(**kw) -> ProposalIn:
    base = dict(id="p1", kind="pay_bill", payee="Acme Paper", account_ref="ACC-1", amount=5_000, proposed_idx=3, bill_kind="supplier", ref="INV-1")
    base.update(kw)
    return ProposalIn(**base)


def verdict(p, c=None):
    c = c or ctx()
    return decide(p, c, set())


def check(d, name):
    return next(c for c in d.checks if c["rule"] == name)


# ---- ALLOW -------------------------------------------------------------------------
def test_allow_when_chance_is_high():
    d = verdict(bill())
    assert d.verdict == "ALLOW" and d.release_idx == 3
    assert check(d, "min_balance_chance")["result"] == "pass"
    assert "Safe to pay Acme Paper RM 5,000" in d.why


def test_every_check_is_in_the_trace_in_rule_order():
    d = verdict(bill())
    assert [c["rule"] for c in d.checks] == ["kill_switch", "statutory_first", "protected_payee", "duplicate_or_anomaly", "approval_limit", "mandate", "min_balance_chance"]


# ---- HOLD ----------------------------------------------------------------------------
def test_hold_with_earliest_safe_date_after_the_dip():
    s = scen(level=45_000, dip_day=10, dip=15_000)
    c = ctx(s, receipts=[Receipt(20, "Big Customer", 30_000)])
    d = verdict(bill(amount=18_400, proposed_idx=10), c)
    assert d.verdict == "HOLD"
    assert d.release_idx is not None and d.release_idx >= 20  # not before the dip is over
    assert check(d, "min_balance_chance")["result"] == "fail"
    assert "Big Customer" in d.why and "Releasing on" in d.why


def test_hold_without_safe_date_says_so():
    s = scen(level=21_000)  # even the last day is unsafe for a 5k payment
    d = verdict(bill(), ctx(s))
    assert d.verdict == "HOLD" and d.release_idx is None and "no day" in d.why


def test_paying_later_is_never_less_safe():
    s = scen(level=45_000, dip_day=10, dip=15_000)
    zero = np.zeros(H + 1)
    ps = []
    for i in range(0, H + 1, 5):
        add = np.zeros(H + 1); add[i:] = 18_400
        ps.append(s.p_ok(zero + add, 20_000))
    assert all(b >= a - 1e-9 for a, b in zip(ps, ps[1:]))


# ---- ESCALATE -------------------------------------------------------------------------
def test_escalate_above_approval_limit():
    d = verdict(bill(amount=30_000), ctx(scen(level=200_000)))
    assert d.verdict == "ESCALATE"
    assert check(d, "approval_limit")["result"] == "fail"


def test_escalate_new_payee():
    d = verdict(bill(payee="Brand New Ltd", account_ref="ACC-9", amount=2_000))
    assert d.verdict == "ESCALATE" and "new payee" in d.why
    assert "new_payee" in check(d, "duplicate_or_anomaly")["anomalies"]


def test_escalate_quarantined_document():
    d = verdict(bill(quarantined=True))
    assert d.verdict == "ESCALATE" and "quarantined" in d.why


def test_escalate_changed_bank_account_for_unprotected_payee():
    d = verdict(bill(account_ref="ACC-OTHER"))
    assert d.verdict == "ESCALATE" and "bank account differs" in d.why


def test_escalate_unusually_large_amount():
    d = verdict(bill(amount=24_500), ctx(scen(level=200_000)))
    assert d.verdict == "ESCALATE" and "over 3x" in d.why


def test_owner_approval_clears_soft_flags_but_not_the_chance_gate():
    ok = verdict(bill(amount=30_000, owner_approved=True), ctx(scen(level=200_000)))
    assert ok.verdict == "ALLOW"
    s = scen(level=45_000, dip_day=10, dip=15_000)
    held = verdict(bill(amount=30_000, owner_approved=True, proposed_idx=10), ctx(s))
    assert held.verdict == "HOLD"  # approval is not a bypass of the minimum-balance rule


# ---- DENY ------------------------------------------------------------------------------
def test_deny_when_kill_switch_is_on_even_for_statutory():
    c = ctx(r=rules(kill_switch=True))
    assert verdict(bill(), c).verdict == "DENY"
    stat = bill(payee="EPF (statutory)", account_ref="GOV-EPF", bill_kind="statutory", ref="EPF-1", amount=5_000)
    d = verdict(stat, c)
    assert d.verdict == "DENY" and "kill switch" in d.why.lower()


def test_deny_protected_payee_with_different_bank_details():
    d = verdict(bill(payee="Protected Co", account_ref="ACC-EVIL"))
    assert d.verdict == "DENY" and check(d, "protected_payee")["result"] == "fail"


def test_deny_duplicate_bill():
    c = ctx(paid_refs={("Acme Paper", "INV-1")})
    d = verdict(bill(), c)
    assert d.verdict == "DENY" and "already paid" in d.why
    c2 = ctx()
    out = evaluate_all([bill(id="a"), bill(id="b")], c2)
    assert [x.verdict for x in out] == ["ALLOW", "DENY"]


def test_deny_top_up_when_reserve_is_too_small():
    p = ProposalIn("t", "top_up", "Reserve", "RESERVE", 20_000, 0, "treasury")
    assert verdict(p, ctx(reserve_balance=10_000)).verdict == "DENY"
    big = ProposalIn("t2", "top_up", "Reserve", "RESERVE", 40_000, 0, "treasury")
    assert verdict(big, ctx(reserve_balance=50_000)).verdict == "ESCALATE"  # above the approval limit, so the owner is asked
    assert verdict(p, ctx(reserve_balance=50_000)).verdict == "ALLOW"


# ---- statutory first ---------------------------------------------------------------------
def test_statutory_and_payroll_are_never_delayed_or_escalated():
    s = scen(level=30_000, dip_day=5, dip=15_000)
    stat = bill(payee="EPF (statutory)", account_ref="GOV-EPF", bill_kind="statutory", ref="EPF-1", amount=40_000, proposed_idx=5)
    d = verdict(stat, ctx(s))
    assert d.verdict == "ALLOW" and d.release_idx == 5  # above approval limit, below minimum: still released
    assert check(d, "min_balance_chance")["result"] == "warn"
    assert "never delays" in d.why


def test_statutory_is_scheduled_before_optional_bills_in_evaluate_all():
    out = evaluate_all([bill(id="x")], ctx())
    assert out[0].proposal_id == "x"


# ---- the chance constraint is joint --------------------------------------------------------
def test_each_released_payment_is_committed_before_the_next_is_judged():
    s = scen(level=50_000)  # room for ~25k above the 20k minimum at 90% confidence
    c = ctx(s)
    out = evaluate_all([bill(id=f"b{i}", ref=f"R{i}", amount=9_000) for i in range(5)], c)
    verdicts = [d.verdict for d in out]
    assert verdicts[:3] == ["ALLOW"] * 3 and "HOLD" in verdicts[3:]
    assert s.p_ok(c.committed, 20_000) >= 0.90  # the whole plan, not just each payment, meets the target


def test_escalated_and_denied_payments_do_not_crowd_out_others():
    c = ctx(scen(level=60_000))
    before = c.committed.copy()
    decide(bill(payee="Brand New Ltd", account_ref="X", amount=48_000), c, set())
    assert np.array_equal(before, c.committed)


def test_risk_tolerance_changes_the_verdict():
    s = scen(level=45_000, dip_day=10, dip=15_000)
    p = bill(amount=9_000, proposed_idx=10)
    strict = verdict(p, ctx(s, rules(risk_tolerance=0.01)))
    loose = verdict(p, ctx(s, rules(risk_tolerance=0.40)))
    assert strict.verdict == "HOLD" and loose.verdict == "ALLOW"


def test_decision_why_is_bilingual():
    d = verdict(bill())
    assert d.why_ms.startswith("Selamat membayar") and d.why != d.why_ms
