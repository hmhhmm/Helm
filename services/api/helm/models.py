"""Schema. One database, separate tables (brief section 6).

facts:      customers, suppliers (payee registry), invoices, bills, balances, documents
rules:      the owner's cash policy. Agents never receive a session that can write it;
            they get a frozen RulesView (see helm.rules_view). On Postgres the grants in
            infra/postgres-init.sql make this a database-level guarantee too.
hand-offs:  cash_range, chase_ideas, bill_plan -> proposals -> decisions -> instructions -> receipts
audit_log:  append-only (DB triggers), hash-chained
sim_*:      the simulated world (hidden truth). Agents never read these tables.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from helm.db import Base


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    terms_days: Mapped[int] = mapped_column(Integer)
    tone: Mapped[str] = mapped_column(String(16), default="friendly")  # friendly | firm


class Supplier(Base):
    """Payee registry. kind: supplier | statutory | payroll."""
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16), default="supplier")
    terms_days: Mapped[int] = mapped_column(Integer, default=30)
    account_ref: Mapped[str] = mapped_column(String(64))


class Document(Base):
    """Raw inbox item and what the Reader Agent extracted from it."""
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # invoice | bill
    received_on: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(32))  # ledger | supplier_email | customer_message
    raw_text: Mapped[str] = mapped_column(Text)
    reader_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    linked_id: Mapped[str | None] = mapped_column(String(24), nullable=True)


class Invoice(Base):
    """Money owed TO the business."""
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    number: Mapped[str] = mapped_column(String(32))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Float)
    issued: Mapped[date] = mapped_column(Date)
    due: Mapped[date] = mapped_column(Date)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="ledger")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    late_signal_days: Mapped[int] = mapped_column(Integer, default=0)
    chased_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    doc_id: Mapped[str | None] = mapped_column(String(24), nullable=True)


class Bill(Base):
    """Money the business OWES. kind: supplier | payroll | statutory."""
    __tablename__ = "bills"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="supplier")
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    payee: Mapped[str] = mapped_column(String(120))
    ref: Mapped[str] = mapped_column(String(48))
    account_ref: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    issued: Mapped[date] = mapped_column(Date)
    due: Mapped[date] = mapped_column(Date)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="ledger")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    doc_id: Mapped[str | None] = mapped_column(String(24), nullable=True)


class Balance(Base):
    __tablename__ = "balances"
    on: Mapped[date] = mapped_column(Date, primary_key=True)
    account: Mapped[str] = mapped_column(String(16), primary_key=True, default="operating")
    amount: Mapped[float] = mapped_column(Float)


class Rules(Base):
    __tablename__ = "rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    min_balance: Mapped[float] = mapped_column(Float, default=20000)
    risk_tolerance: Mapped[float] = mapped_column(Float, default=0.10)  # alpha
    approval_limit: Mapped[float] = mapped_column(Float, default=25000)
    protected_payees: Mapped[list] = mapped_column(JSON, default=list)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=90)


class SimState(Base):
    __tablename__ = "sim_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    today: Mapped[date] = mapped_column(Date)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)


class SimTruth(Base):
    """Hidden world: when an open invoice will really be paid. Agents never read this."""
    __tablename__ = "sim_truth"
    invoice_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    pay_date: Mapped[date] = mapped_column(Date)


class SimFuture(Base):
    """Hidden world: documents that will arrive in the inbox as time advances."""
    __tablename__ = "sim_future"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    arrive_on: Mapped[date] = mapped_column(Date)
    raw_text: Mapped[str] = mapped_column(Text)
    truth_pay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    ts: Mapped[str] = mapped_column(String(32))
    sim_date: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(String(16))  # full | gate
    trigger: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="ok")


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    node: Mapped[str] = mapped_column(String(24))  # reader, forecaster, ... policy, human, executor, explainer, watchdog
    status: Mapped[str] = mapped_column(String(16))  # ok | skipped | error
    ms: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class CashRange(Base):
    """Forecaster output. summary = quantile bands; paths_blob = compressed scenario matrix."""
    __tablename__ = "cash_range"
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict] = mapped_column(JSON)
    paths_blob: Mapped[bytes] = mapped_column(LargeBinary)


class ChaseIdea(Base):
    __tablename__ = "chase_ideas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    rank: Mapped[int] = mapped_column(Integer)
    effect_rm: Mapped[float] = mapped_column(Float)
    amount_open: Mapped[float] = mapped_column(Float)
    invoice_ids: Mapped[list] = mapped_column(JSON)
    tone: Mapped[str] = mapped_column(String(16))
    why: Mapped[str] = mapped_column(Text)
    draft_en: Mapped[str] = mapped_column(Text)
    draft_ms: Mapped[str] = mapped_column(Text)


class BillPlan(Base):
    __tablename__ = "bill_plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    bill_id: Mapped[str] = mapped_column(String(16))
    rank: Mapped[int] = mapped_column(Integer)
    due: Mapped[date] = mapped_column(Date)
    plan_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = beyond horizon
    days_late: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # pay_bill | sweep | top_up
    bill_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    payee: Mapped[str] = mapped_column(String(120))
    account_ref: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Float)
    proposed_date: Mapped[date] = mapped_column(Date)
    origin: Mapped[str] = mapped_column(String(24))  # which agent wrote it
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | executed | superseded | held_by_owner
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(32))


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    verdict: Mapped[str] = mapped_column(String(16))
    release_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    checks: Mapped[list] = mapped_column(JSON)
    why: Mapped[str] = mapped_column(Text)
    why_ms: Mapped[str] = mapped_column(Text, default="")
    p_ok: Mapped[float | None] = mapped_column(Float, nullable=True)
    consequence: Mapped[dict] = mapped_column(JSON, default=dict)
    owner_choice: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))


class Instruction(Base):
    __tablename__ = "instructions"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    proposal_id: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(32))


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    instruction_id: Mapped[str] = mapped_column(ForeignKey("instructions.id"))
    proposal_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))  # accepted | rejected
    payload: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)  # Explainer Agent
    sim_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[str] = mapped_column(String(32))


class BankLedger(Base):
    """The Demo bank's own books. Helm never writes here except through the bank API."""
    __tablename__ = "bank_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instruction_id: Mapped[str] = mapped_column(String(24))
    ts: Mapped[str] = mapped_column(String(32))
    from_account: Mapped[str] = mapped_column(String(16))
    to_account: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(160), default="")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(12))  # info | warn | critical
    source: Mapped[str] = mapped_column(String(24))
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    """Append-only. hash = sha256(prev_hash + canonical_json(row))."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(32))
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
