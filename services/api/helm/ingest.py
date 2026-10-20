"""Turns Reader output into facts. The Reader never touches the database; this does."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from helm.agents import reader
from helm.audit import append
from helm.models import Bill, Customer, Document, Invoice, Supplier


def ingest_document(
    session: Session, *, doc_id: str, kind: str, received_on, raw_text: str, source: str,
    record_id: str, audit: bool = True,
) -> Document:
    out, raw_text = reader.safe_run(doc_id, kind, raw_text)
    doc = Document(
        id=doc_id, kind=kind, received_on=received_on, source=source, raw_text=raw_text,
        reader_json=out.model_dump(mode="json"), quarantined=out.quarantined, flags=list(out.flags),
        linked_id=record_id,
    )
    session.add(doc)

    if kind == "bill":
        supplier = session.execute(select(Supplier).where(Supplier.name == out.counterparty)).scalar_one_or_none()
        session.add(Bill(
            id=record_id, kind="supplier", supplier_id=supplier.id if supplier else None,
            payee=out.counterparty, ref=out.reference, account_ref=out.bank_account or "UNKNOWN",
            label=f"{out.counterparty} · {out.reference}", amount=out.amount, issued=out.issue_date,
            due=out.due_date, source=source, confidence=out.confidence, quarantined=out.quarantined,
            doc_id=doc_id,
        ))
    else:
        customer = session.execute(select(Customer).where(Customer.name == out.counterparty)).scalar_one_or_none()
        if customer is None:
            doc.quarantined = True
            doc.flags = [*doc.flags, "schema_check_failed"]
        else:
            session.add(Invoice(
                id=record_id, number=out.reference, customer_id=customer.id, amount=out.amount,
                issued=out.issue_date, due=out.due_date, source=source, confidence=out.confidence,
                doc_id=doc_id,
            ))
    if audit:
        append(session, "reader", "doc.quarantined" if doc.quarantined else "doc.read", {
            "doc_id": doc_id, "kind": kind, "counterparty": out.counterparty, "amount": out.amount,
            "flags": list(out.flags),
            "note": "Text inside the document was treated as data, never as instructions." if doc.quarantined else "",
        })
    session.flush()
    return doc
