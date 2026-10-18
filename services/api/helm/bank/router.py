from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.bank import service
from helm.db import get_session
from helm.models import BankLedger

router = APIRouter(prefix="/bank", tags=["demo-bank"])


class InstructionIn(BaseModel):
    instruction_id: str
    from_account: str = "operating"
    to_account: str
    amount: float
    scope: str


@router.post("/instructions")
def submit(body: InstructionIn, x_bank_key: str = Header(...), session: Session = Depends(get_session)):
    out = service.submit(session, key=x_bank_key, **body.model_dump())
    session.commit()
    return out


@router.get("/ledger")
def ledger(session: Session = Depends(get_session)):
    rows = session.execute(select(BankLedger).order_by(BankLedger.id.desc()).limit(50)).scalars().all()
    return {"bank": "Demo bank (not a real bank)", "rows": [
        {"id": r.id, "ts": r.ts, "from": r.from_account, "to": r.to_account, "amount": r.amount, "status": r.status, "reason": r.reason if not r.reason.startswith("nonce:") else ""}
        for r in rows
    ]}
