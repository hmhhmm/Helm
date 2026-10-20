"""Policy Engine (CODE, pure functions). Only this module can say a payment may go.

Rule order: kill switch -> statutory first -> protected payee -> duplicate / anomaly ->
approval limit -> chance constraint -> verdict.

  DENY      a hard rule failed (kill switch, protected payee's bank details changed, duplicate)
  ESCALATE  needs the owner (above the approval limit, new payee, anomaly)
  HOLD      the chance of staying above the minimum balance is too low; carries the earliest safe date
  ALLOW     safe to release

Chance constraint:  P( min_{t<=H} balance_t >= B | pay )  >=  1 - alpha
"""
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from helm.fmt import fdate, pct, rm
from helm.forecast.montecarlo import ScenarioSet
from helm.rules_view import RulesView

VERDICTS = ("ALLOW", "HOLD", "ESCALATE", "DENY")


@dataclass(frozen=True)
class Payee:
    name: str
    account_ref: str
    kind: str  # supplier | statutory | payroll
    typical_amount: float | None = None


@dataclass(frozen=True)
class ProposalIn:
    id: str
    kind: str  # pay_bill | sweep | top_up
    payee: str
    account_ref: str
    amount: float
    proposed_idx: int  # day index the proposal wants to pay on (>= 0)
    bill_kind: str = "supplier"  # supplier | payroll | statutory (for pay_bill)
    ref: str = ""
    quarantined: bool = False
    owner_approved: bool = False
    due_idx: int = 0


@dataclass(frozen=True)
class Receipt:
    """A known invoice the forecast expects to land (used to explain *why* a date is safe)."""
    idx: int
    customer: str
    amount: float


@dataclass
class PolicyContext:
    rules: RulesView
    today: date
    scen: ScenarioSet
    registry: dict[str, Payee]
    paid_refs: set[tuple[str, str]] = field(default_factory=set)  # (payee, ref) already paid
    receipts: list[Receipt] = field(default_factory=list)
    reserve_balance: float = 0.0
    sent_by_day: dict = field(default_factory=dict)  # money already sent through the bank, by date
    committed_by_day: dict = field(default_factory=dict)  # money released in this pass, by date
    committed: np.ndarray | None = None  # cumulative outflow by day, grows as decisions land

    def __post_init__(self):
        if self.committed is None:
            self.committed = np.zeros(self.scen.horizon + 1)


@dataclass
class Decision:
    proposal_id: str
    verdict: str
    release_idx: int | None
    release_on: date | None
    checks: list[dict]
    why: str
    why_ms: str
    p_ok: float | None
    consequence: dict = field(default_factory=dict)  # for the approval card


def _outflow(H: int, idx: int, amount: float) -> np.ndarray:
    v = np.zeros(H + 1)
    v[idx:] = amount
    return v


def _low_point(ctx: PolicyContext, committed: np.ndarray) -> dict:
    p10 = ctx.scen.bands(committed)["p10"]
    i = int(np.argmin(p10))
    return {"date": ctx.scen.day(i).isoformat(), "rm": round(float(p10[i]))}


def _cause(ctx: PolicyContext, from_idx: int, to_idx: int, lang: str) -> str:
    best = None
    for r in ctx.receipts:
        if from_idx < r.idx <= to_idx and (best is None or r.amount > best.amount):
            best = r
    if best is None:
        return "once more cash is expected" if lang == "en" else "apabila lebih banyak tunai dijangka masuk"
    d = fdate(ctx.scen.day(best.idx), lang)
    if lang == "en":
        return f"after {best.customer} pays {rm(best.amount)} (expected {d})"
    return f"selepas {best.customer} membayar {rm(best.amount)} (dijangka {d})"


def _reasons_text(reasons: list[tuple[str, str]], lang: str) -> str:
    idx = 0 if lang == "en" else 1
    return "; ".join(r[idx] for r in reasons)


def decide(p: ProposalIn, ctx: PolicyContext, seen_in_pass: set[tuple[str, str]]) -> Decision:
    """One proposal -> one decision with a full trace. Mutates ctx.committed when money is released."""
    rules, scen = ctx.rules, ctx.scen
    B, req, H = rules.min_balance, rules.required_confidence, scen.horizon
    checks: list[dict] = []
    hard: list[tuple[str, str]] = []  # (en, ms)
    soft: list[tuple[str, str]] = []
    payee = ctx.registry.get(p.payee)
    is_transfer = p.kind in ("sweep", "top_up")
    exempt = p.kind == "pay_bill" and p.bill_kind in ("statutory", "payroll")
    day = fdate(scen.day(p.proposed_idx))
    day_ms = fdate(scen.day(p.proposed_idx), "ms")
    amt = rm(p.amount)

    # 1. kill switch -----------------------------------------------------------------
    if rules.kill_switch:
        checks.append({"rule": "kill_switch", "result": "fail", "detail": "Kill switch is on"})
        why = f"The kill switch is on, so Helm will not move {amt} to {p.payee}."
        why_ms = f"Suis pemutus aktif, jadi Helm tidak akan memindahkan {amt} kepada {p.payee}."
        return Decision(p.id, "DENY", None, None, checks, why, why_ms, None)
    checks.append({"rule": "kill_switch", "result": "pass"})

    # 2. statutory first -------------------------------------------------------------
    if exempt:
        checks.append({"rule": "statutory_first", "result": "pass", "detail": "Statutory/payroll items are scheduled first and never delayed"})
    else:
        checks.append({"rule": "statutory_first", "result": "pass", "detail": "Not a statutory item; paid after statutory items are secured"})

    # 3. protected payee -------------------------------------------------------------
    protected = p.payee in rules.protected_payees or (payee is not None and payee.kind != "supplier")
    if is_transfer:
        checks.append({"rule": "protected_payee", "result": "pass", "detail": "Internal transfer between the owner's own accounts"})
    elif payee is not None and protected and p.account_ref != payee.account_ref:
        hard.append((f"{p.payee} is a protected payee and the bank details on this bill do not match the ones on file",
                     f"{p.payee} ialah penerima dilindungi dan butiran bank pada bil ini tidak sepadan dengan rekod"))
        checks.append({"rule": "protected_payee", "result": "fail", "on_file": payee.account_ref, "on_bill": p.account_ref})
    else:
        checks.append({"rule": "protected_payee", "result": "pass", "detail": "Protected payee, bank details match" if protected else "Not a protected payee"})

    # 4. duplicate / anomaly ---------------------------------------------------------
    anomalies: list[str] = []
    key = (p.payee, p.ref)
    duplicate = bool(p.ref) and (key in ctx.paid_refs or key in seen_in_pass)
    if duplicate:
        hard.append((f"a bill with reference {p.ref} from {p.payee} was already paid or queued",
                     f"bil dengan rujukan {p.ref} daripada {p.payee} sudah dibayar atau dalam barisan"))
    if p.kind == "pay_bill":
        if payee is None:
            anomalies.append("new_payee")
            soft.append((f"{p.payee} is a new payee Helm has never paid",
                         f"{p.payee} ialah penerima baharu yang tidak pernah dibayar Helm"))
        elif p.account_ref != payee.account_ref and not protected:
            anomalies.append("bank_details_changed")
            soft.append(("the bank account differs from the one on file", "akaun bank berbeza daripada rekod"))
        if p.quarantined:
            anomalies.append("quarantined_document")
            soft.append(("the document was quarantined because it contained instructions", "dokumen dikuarantin kerana mengandungi arahan"))
        if payee and payee.typical_amount and p.amount > 3 * payee.typical_amount and p.amount > 5000:
            anomalies.append("unusual_amount")
            soft.append((f"the amount is over 3x what {p.payee} usually bills", f"jumlah melebihi 3x daripada kebiasaan {p.payee}"))
    checks.append({
        "rule": "duplicate_or_anomaly",
        "result": "fail" if duplicate else ("flag" if anomalies else "pass"),
        **({"anomalies": anomalies} if anomalies else {}),
        **({"duplicate_of": p.ref} if duplicate else {}),
    })
    if p.owner_approved and not duplicate:
        soft = []  # the owner has looked at this and said yes

    # 5. approval limit --------------------------------------------------------------
    over = (not exempt) and p.amount > rules.approval_limit
    if over and not p.owner_approved:
        soft.append((f"{amt} is above your approval limit of {rm(rules.approval_limit)}",
                     f"{amt} melebihi had kelulusan anda {rm(rules.approval_limit)}"))
        checks.append({"rule": "approval_limit", "result": "fail", "limit": rules.approval_limit, "amount": p.amount})
    else:
        checks.append({"rule": "approval_limit", "result": "pass",
                       **({"detail": "Exempt: recurring statutory/payroll"} if exempt else {}),
                       **({"detail": "Approved by the owner"} if over and p.owner_approved else {})})

    # 5b. mandate: expiry, daily cap, monthly cap ------------------------------------------
    if p.kind == "pay_bill":
        rel_date = scen.day(p.proposed_idx)
        reasons: list[tuple[str, str]] = []
        detail: dict = {}
        if rules.mandate_expires and rel_date > rules.mandate_expires:
            reasons.append((f"your mandate ended on {fdate(rules.mandate_expires)}, so nothing is automatic any more",
                            f"mandat anda tamat pada {fdate(rules.mandate_expires, 'ms')}, jadi tiada yang automatik lagi"))
            detail["expired_on"] = rules.mandate_expires.isoformat()
        if not exempt:
            day_total = ctx.sent_by_day.get(rel_date, 0.0) + ctx.committed_by_day.get(rel_date, 0.0) + p.amount
            if rules.daily_cap is not None and day_total > rules.daily_cap:
                reasons.append((f"it would take {fdate(rel_date)} to {rm(day_total)}, above your daily cap of {rm(rules.daily_cap)}",
                                f"ia menjadikan {fdate(rel_date, 'ms')} {rm(day_total)}, melebihi had harian {rm(rules.daily_cap)}"))
                detail.update(daily_cap=rules.daily_cap, day_total=round(day_total))
            sent_m = sum(v for d_, v in ctx.sent_by_day.items() if (d_.year, d_.month) == (rel_date.year, rel_date.month))
            comm_m = sum(v for d_, v in ctx.committed_by_day.items() if (d_.year, d_.month) == (rel_date.year, rel_date.month))
            month_total = sent_m + comm_m + p.amount
            if rules.monthly_cap is not None and month_total > rules.monthly_cap:
                reasons.append((f"it would take the month to {rm(month_total)}, above your monthly cap of {rm(rules.monthly_cap)}",
                                f"ia menjadikan bulan ini {rm(month_total)}, melebihi had bulanan {rm(rules.monthly_cap)}"))
                detail.update(monthly_cap=rules.monthly_cap, month_total=round(month_total))
        if reasons and not p.owner_approved:
            soft.extend(reasons)
            checks.append({"rule": "mandate", "result": "fail", **detail})
        else:
            checks.append({"rule": "mandate", "result": "pass", **({"detail": "Approved by the owner"} if reasons else {})})
    else:
        checks.append({"rule": "mandate", "result": "pass", "detail": "Internal transfer"})

    # 6. chance constraint -------------------------------------------------------------
    baseline_p = scen.p_ok(ctx.committed, B)
    if p.kind == "top_up":
        p_after = scen.p_ok(ctx.committed - _outflow(H, p.proposed_idx, p.amount), B)
        enough = ctx.reserve_balance >= p.amount
        checks.append({"rule": "min_balance_chance", "result": "pass", "p_ok": round(p_after, 3), "required": req,
                       "detail": "A top-up adds cash, so it cannot make the chance worse"})
        if not enough:
            hard.append((f"the reserve holds only {rm(ctx.reserve_balance)}", f"rizab hanya ada {rm(ctx.reserve_balance)}"))
            checks.append({"rule": "reserve_covers", "result": "fail", "reserve": ctx.reserve_balance})
        verdict = "DENY" if hard else ("ESCALATE" if soft else "ALLOW")
        rel = p.proposed_idx if verdict == "ALLOW" else None
        why = (f"Safe to move {amt} from the reserve to the operating account on {day}; it lifts the chance of staying above {rm(B)} from {pct(baseline_p)} to {pct(p_after)}."
               if verdict == "ALLOW" else f"Cannot move {amt}: {_reasons_text(hard or soft, 'en')}.")
        why_ms = (f"Selamat memindahkan {amt} daripada rizab ke akaun operasi pada {day_ms}; ia menaikkan peluang kekal melebihi {rm(B)} daripada {pct(baseline_p)} kepada {pct(p_after)}."
                  if verdict == "ALLOW" else f"Tidak boleh memindahkan {amt}: {_reasons_text(hard or soft, 'ms')}.")
        return Decision(p.id, verdict, rel, scen.day(rel) if rel is not None else None, checks, why, why_ms, p_after,
                        {"p_if_done": p_after, "p_if_skipped": baseline_p})

    add_now = _outflow(H, p.proposed_idx, p.amount)
    p_now = scen.p_ok(ctx.committed + add_now, B)
    chance_ok = p_now >= req
    low = _low_point(ctx, ctx.committed + add_now)
    if exempt:
        checks.append({
            "rule": "min_balance_chance", "result": "pass" if chance_ok else "warn", "p_ok": round(p_now, 3), "required": req,
            "low_point": low, "detail": "Statutory/payroll is released on time regardless; Helm warns instead of delaying",
        })
    else:
        checks.append({
            "rule": "min_balance_chance", "result": "pass" if chance_ok else "fail", "p_ok": round(p_now, 3),
            "required": req, "low_point": low, "baseline_p_ok": round(baseline_p, 3),
        })

    # earliest safe date (needed for HOLD and for the consequence shown to the owner)
    safe_idx: int | None = p.proposed_idx
    if not chance_ok and not exempt:
        safe_idx = scen.earliest_safe_idx(ctx.committed, p.amount, p.proposed_idx, B, req)

    consequence = {"p_if_paid": p_now, "p_if_held": baseline_p, "low_point_if_paid": low, "safe_date": scen.day(safe_idx).isoformat() if safe_idx is not None else None}

    # verdict -------------------------------------------------------------------------
    if hard:
        verdict, rel = "DENY", None
        why = f"Blocked: {_reasons_text(hard, 'en')}. No money moved."
        why_ms = f"Disekat: {_reasons_text(hard, 'ms')}. Tiada wang dipindahkan."
    elif soft:
        verdict, rel = "ESCALATE", safe_idx
        when = f" If you approve, Helm releases it on {fdate(scen.day(safe_idx))} once it is safe." if safe_idx is not None else ""
        when_ms = f" Jika anda lulus, Helm melepaskannya pada {fdate(scen.day(safe_idx), 'ms')} apabila selamat." if safe_idx is not None else ""
        why = f"Needs your OK: {_reasons_text(soft, 'en')}.{when}"
        why_ms = f"Perlu kelulusan anda: {_reasons_text(soft, 'ms')}.{when_ms}"
    elif exempt:
        verdict, rel = "ALLOW", p.proposed_idx
        warn = ""
        warn_ms = ""
        if not chance_ok:
            warn = f" Heads-up: paying it leaves a {pct(1 - p_now)} chance of dipping under {rm(B)} around {fdate(date.fromisoformat(low['date']))}; consider a top-up."
            warn_ms = f" Perhatian: membayarnya meninggalkan {pct(1 - p_now)} risiko jatuh bawah {rm(B)} sekitar {fdate(date.fromisoformat(low['date']), 'ms')}; pertimbangkan tambah baki."
        why = f"Statutory payment: Helm pays {p.payee} {amt} on {day} and never delays it.{warn}"
        why_ms = f"Bayaran berkanun: Helm membayar {p.payee} {amt} pada {day_ms} dan tidak pernah menangguhkannya.{warn_ms}"
    elif chance_ok:
        verdict, rel = "ALLOW", p.proposed_idx
        if p.kind == "sweep":
            why = f"Safe to park {amt} in the reserve on {day}: the chance of staying above {rm(B)} remains {pct(p_now)} (you asked for {pct(req)})."
            why_ms = f"Selamat menyimpan {amt} dalam rizab pada {day_ms}: peluang kekal melebihi {rm(B)} ialah {pct(p_now)} (anda minta {pct(req)})."
        else:
            why = f"Safe to pay {p.payee} {amt} on {day}: afterwards there is a {pct(p_now)} chance the balance stays above {rm(B)} (you asked for {pct(req)})."
            why_ms = f"Selamat membayar {p.payee} {amt} pada {day_ms}: selepas itu ada {pct(p_now)} peluang baki kekal melebihi {rm(B)} (anda minta {pct(req)})."
    elif safe_idx is not None:
        verdict, rel = "HOLD", safe_idx
        why = (f"Paying {p.payee} {amt} on {day} leaves a {pct(1 - p_now)} chance of dropping under {rm(B)} "
               f"(lowest around {fdate(date.fromisoformat(low['date']))}). Releasing on {fdate(scen.day(safe_idx))}, "
               f"{_cause(ctx, p.proposed_idx, safe_idx, 'en')}, keeps it above {pct(req)}.")
        why_ms = (f"Membayar {p.payee} {amt} pada {day_ms} meninggalkan {pct(1 - p_now)} risiko jatuh bawah {rm(B)} "
                  f"(paling rendah sekitar {fdate(date.fromisoformat(low['date']), 'ms')}). Dilepaskan pada {fdate(scen.day(safe_idx), 'ms')}, "
                  f"{_cause(ctx, p.proposed_idx, safe_idx, 'ms')}, mengekalkannya melebihi {pct(req)}.")
    else:
        verdict, rel = "HOLD", None
        why = (f"Paying {p.payee} {amt} now leaves a {pct(1 - p_now)} chance of dropping under {rm(B)}, and no day in the next {H} days is safe yet. "
               f"Collect receipts or top up the balance first.")
        why_ms = (f"Membayar {p.payee} {amt} sekarang meninggalkan {pct(1 - p_now)} risiko jatuh bawah {rm(B)}, dan tiada hari dalam {H} hari akan datang yang selamat. "
                  f"Kutip bayaran atau tambah baki dahulu.")

    # commit only what will really be released; escalations wait for the owner
    if verdict in ("ALLOW", "HOLD") and rel is not None and p.kind == "pay_bill":
        rd = scen.day(rel)
        ctx.committed_by_day[rd] = ctx.committed_by_day.get(rd, 0.0) + p.amount
    if verdict in ("ALLOW", "HOLD") and rel is not None and not exempt:
        ctx.committed = ctx.committed + _outflow(H, rel, p.amount)
    if p.ref and verdict in ("ALLOW", "HOLD"):
        seen_in_pass.add(key)

    return Decision(
        p.id, verdict, rel, scen.day(rel) if rel is not None else None, checks, why, why_ms,
        p_now if verdict != "HOLD" else (scen.p_ok(ctx.committed, B) if rel is not None else p_now), consequence,
    )


def evaluate_all(proposals: list[ProposalIn], ctx: PolicyContext) -> list[Decision]:
    """Decide in the given order (statutory first, then the Scheduler's plan order).
    Each released payment is committed before the next is judged, so the final plan as a whole
    satisfies the chance constraint, not just each payment on its own."""
    seen: set[tuple[str, str]] = set()
    out: list[Decision] = []
    for p in proposals:
        out.append(decide(p, ctx, seen))
    return out
