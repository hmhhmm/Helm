"""Response models. They exist so the web client is generated from the OpenAPI spec and typed end to end."""
from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal["ALLOW", "HOLD", "ESCALATE", "DENY"]


class Txt(BaseModel):
    en: str
    ms: str


class Alert(BaseModel):
    id: int
    level: str
    message: str
    ts: str


class StateOut(BaseModel):
    today: str
    synthetic: bool
    kill_switch: bool
    min_balance: float
    operating: float
    reserve: float
    last_run_id: str | None
    demo_mode: bool
    llm_mode: str
    escalations: list[str]
    alerts: list[Alert]
    chain_ok: bool
    chain_broken_at: int | None


class Row(BaseModel):
    proposal_id: str
    payee: str
    amount: float
    kind: str
    bill_kind: str | None = None
    ref: str | None = None
    label: str | None = None
    due: str | None = None
    release_on: str | None = None
    verdict: Verdict
    why: str
    why_ms: str
    previous_verdict: Verdict | None = None
    previous_release_on: str | None = None
    status: Literal["queued", "sent", "held_by_owner"]
    quarantined: bool
    p_ok: float | None = None
    sent_on: str | None = None
    doc_id: str | None = None
    owner_choice: str | None = None


class NeedsYou(BaseModel):
    kind: Literal["approve", "hold", "chase", "alert", "top_up"]
    title: Txt
    detail: Txt
    href: str
    proposal_id: str | None = None


class LowPoint(BaseModel):
    date: str
    p50: float
    worst_date: str
    worst: float
    chance_below_min: float


class Managed(BaseModel):
    p_ok: float
    required: float
    low_p10: float


class TodayOut(BaseModel):
    today: str
    cash_now: float
    reserve: float
    min_balance: float
    buffer_days: float
    runway_days: float
    daily_burn: float
    status: Literal["ok", "watch", "risk"]
    headline: Txt
    low_point: LowPoint
    managed: Managed
    needs_you: list[NeedsYou]
    week_decisions: list[Row]
    kill_switch: bool


class Band(BaseModel):
    p10: list[float]
    p25: list[float]
    p50: list[float]
    p75: list[float]
    p90: list[float]


class Low(BaseModel):
    date: str
    p50: float
    p10: float
    worst_date: str
    worst: float


class ManagedLow(BaseModel):
    date: str
    p50: float
    p10: float


class Event(BaseModel):
    id: str
    date: str
    kind: Literal["bill", "payroll", "statutory", "invoice"]
    label: str
    amount: float
    verdict: Verdict | None = None
    release_on: str | None = None
    proposal_id: str | None = None
    range: list[str] | None = None
    late_signal_days: int | None = None
    customer_id: str | None = None
    number: str | None = None


class Causes(BaseModel):
    bill: Event | None = None
    invoice: Event | None = None


class Snapshot(BaseModel):
    origin: str
    days_checked: int
    inside_80: float
    median_abs_error: float


class TrackRecord(BaseModel):
    snapshots: list[Snapshot]
    days_checked: int
    coverage_80: float | None
    median_abs_error: float | None
    stated_coverage: float
    note: str


class Change(BaseModel):
    proposal_id: str
    payee: str
    amount: float
    from_: Verdict | None = Field(default=None, alias="from")
    to: Verdict
    release_from: str | None = None
    release_to: str | None = None
    why: str
    why_ms: str

    model_config = {"populate_by_name": True}


class PolicyChange(BaseModel):
    payee: str
    amount: float
    from_: Verdict = Field(alias="from")
    to: Verdict
    release_from: str | None = None
    release_to: str | None = None

    model_config = {"populate_by_name": True}


class Baseline(BaseModel):
    low: Low
    p_ok_unmanaged: float
    p_ok_managed: float


class ForecastOut(BaseModel):
    today: str
    days: list[str]
    unmanaged: Band
    managed: Band
    min_balance: float
    start: float
    required: float
    low: Low
    managed_low: ManagedLow
    p_ok_unmanaged: float
    p_ok_managed: float
    events: list[Event]
    causes: Causes
    assumptions: dict[str, Any]
    track_record: TrackRecord
    whatif: bool | None = None
    changes: list[Change] | None = None
    baseline: Baseline | None = None


class LateIn(BaseModel):
    customer_id: str
    days: int


class WhatIfIn(BaseModel):
    late: list[LateIn] = []
    skip_bill_ids: list[str] = []


class PaymentsOut(BaseModel):
    today: str
    groups: dict[str, list[Row]]
    counts: dict[str, int]
    summary: Txt


class Check(BaseModel):
    rule: str
    result: str

    model_config = {"extra": "allow"}


class DocumentOut(BaseModel):
    id: str
    source: str
    received_on: str
    raw_text: str
    extracted: dict[str, Any] | None
    quarantined: bool
    flags: list[str]


class DecisionOut(BaseModel):
    row: Row
    checks: list[Check]
    consequence: dict[str, Any]
    timeline: list[dict[str, str]]
    history: list[dict[str, Any]]
    document: DocumentOut | None
    plan: dict[str, Any] | None
    receipt: dict[str, Any] | None
    min_balance: float
    required: float
    amount: float


class TryOut(BaseModel):
    proposal_id: str
    on: str
    verdict: Verdict
    why: str
    why_ms: str
    release_on: str | None
    checks: list[Check]
    payee: str
    amount: float


class OwnerIn(BaseModel):
    choice: Literal["approve", "hold"]


class AgeInvoice(BaseModel):
    id: str
    number: str
    customer_id: str
    customer: str
    amount: float
    issued: str
    due: str
    days_overdue: int
    expected: str | None
    chased_on: str | None
    late_signal_days: int
    doc_id: str | None


class Idea(BaseModel):
    customer_id: str
    customer: str
    rank: int
    effect_rm: float
    amount_open: float
    invoice_ids: list[str]
    tone: str
    why: str
    draft_en: str
    draft_ms: str
    avg_delay: float
    paid_count: int


class DsoPoint(BaseModel):
    month: str
    dso: float


class Dso(BaseModel):
    series: list[DsoPoint]
    current: float | None


class CollectionsOut(BaseModel):
    today: str
    ageing: dict[str, list[AgeInvoice]]
    ideas: list[Idea]
    dso: Dso
    total_open: float
    assumption_days: int
    summary: Txt


class ToneIn(BaseModel):
    tone: Literal["friendly", "firm"]


class CashIdea(Row):
    direction: str | None = None
    reason: str | None = None
    reason_ms: str | None = None
    interest_estimate: float | None = None
    on: str


class HistPoint(BaseModel):
    month: str
    money_in: float
    money_out: float


class CashOut(BaseModel):
    history: list[HistPoint]
    today: str
    operating: float
    reserve: float
    min_balance: float
    comfort: float
    ideas: list[CashIdea]
    apy: float
    apy_note: str
    p_ok_unmanaged: float
    p_ok_managed: float
    summary: Txt


class SupplierOut(BaseModel):
    name: str
    kind: str


class PolicyOut(BaseModel):
    today: str
    min_balance: float
    risk_tolerance: float
    required_confidence: float
    approval_limit: float
    protected_payees: list[str]
    kill_switch: bool
    suppliers: list[SupplierOut]
    risk_options: list[float]
    examples: dict[str, Txt]


class PolicyIn(BaseModel):
    min_balance: float
    risk_tolerance: float
    approval_limit: float
    protected_payees: list[str]


class PolicyPreview(BaseModel):
    counts: dict[str, int]
    baseline: dict[str, int]
    changes: list[PolicyChange]


class Step(BaseModel):
    status: str
    ms: int
    summary: str
    run_id: str


class Node(BaseModel):
    id: str
    n: int | None = None
    label: str
    kind: str
    reads: list[str]
    writes: list[str]
    note: str
    step: Step | None = None


class LogLine(BaseModel):
    id: int
    run_id: str
    sim_date: str
    mode: str
    trigger: str
    node: str
    status: str
    ms: int
    summary: str


class AlertFull(BaseModel):
    id: int
    level: str
    message: str
    ts: str
    resolved: bool


class LastRun(BaseModel):
    id: str
    ts: str
    mode: str
    trigger: str
    sim_date: str


class AgentsOut(BaseModel):
    nodes: list[Node]
    log: list[LogLine]
    alerts: list[AlertFull]
    kill_switch: bool
    llm_mode: str
    last_run: LastRun | None
    audit_rows: int


class AuditRow(BaseModel):
    id: int
    ts: str
    actor: str
    event: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


class AuditPage(BaseModel):
    rows: list[AuditRow]
    total: int


class VerifyOut(BaseModel):
    ok: bool
    checked: int
    broken_at: int | None
    reason: str | None


class KillIn(BaseModel):
    on: bool


class SimOut(BaseModel):
    ok: bool = True
    message: str
    data: dict[str, Any] = {}
