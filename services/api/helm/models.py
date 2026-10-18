"""Schema. One database, separate tables (see brief section 6).

facts:      customers, suppliers, invoices, bills, balances, statutory_items
rules:      owner's cash policy (agents get a read-only role in Postgres)
hand-offs:  proposals -> decisions -> instructions -> receipts
audit_log:  append-only, hash-chained
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from helm.db import Base


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    terms_days: Mapped[int] = mapped_column(Integer)
    tone: Mapped[str] = mapped_column(String(16), default="friendly")


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    terms_days: Mapped[int] = mapped_column(Integer)
    account_ref: Mapped[str] = mapped_column(String(64))
    protected: Mapped[bool] = mapped_column(Boolean, default=False)


class Invoice(Base):
    """Money owed TO the business."""
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Float)
    issued: Mapped[date] = mapped_column(Date)
    due: Mapped[date] = mapped_column(Date)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="ledger")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)


class Bill(Base):
    """Money the business OWES."""
    __tablename__ = "bills"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="supplier")  # supplier | payroll | statutory
    label: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    issued: Mapped[date] = mapped_column(Date)
    due: Mapped[date] = mapped_column(Date)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="ledger")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)


class Balance(Base):
    __tablename__ = "balances"
    on: Mapped[date] = mapped_column(Date, primary_key=True)
    amount: Mapped[float] = mapped_column(Float)
    account: Mapped[str] = mapped_column(String(16), primary_key=True, default="operating")


class Rules(Base):
    __tablename__ = "rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    min_balance: Mapped[float] = mapped_column(Float, default=20000)
    risk_tolerance: Mapped[float] = mapped_column(Float, default=0.10)  # alpha
    approval_limit: Mapped[float] = mapped_column(Float, default=15000)
    protected_payees: Mapped[list] = mapped_column(JSON, default=list)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    horizon_days: Mapped[int] = mapped_column(Integer, default=90)


class SimState(Base):
    __tablename__ = "sim_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    today: Mapped[date] = mapped_column(Date)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # pay_bill | sweep | top_up
    bill_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    payee: Mapped[str] = mapped_column(String(120))
    account_ref: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Float)
    proposed_date: Mapped[date] = mapped_column(Date)
    origin: Mapped[str] = mapped_column(String(32))  # which agent wrote it
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    verdict: Mapped[str] = mapped_column(String(16))
    release_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    checks: Mapped[list] = mapped_column(JSON)
    why: Mapped[str] = mapped_column(Text)
    owner_choice: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Instruction(Base):
    __tablename__ = "instructions"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    instruction_id: Mapped[str] = mapped_column(ForeignKey("instructions.id"))
    status: Mapped[str] = mapped_column(String(16))  # accepted | rejected
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AuditLog(Base):
    """Append-only. hash = sha256(prev_hash + canonical_json(row))."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(32))
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
