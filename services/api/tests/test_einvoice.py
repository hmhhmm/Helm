from helm import audit  # noqa: F401
from helm.models import Invoice
from tests.conftest import owner_client  # noqa: F401
from fastapi.testclient import TestClient
from helm.main import app


def test_einvoice_document_matches_the_ledger_and_is_not_submitted():
    with TestClient(app) as c:
        iid = c.get("/collections").json()["ageing"]["not_due"][0]["id"]
        r = c.get(f"/invoices/{iid}/einvoice").json()
        inv = r["document"]["Invoice"][0]
        assert r["submitted"] is False and r["status"] == "ready_to_submit"
        assert inv["LegalMonetaryTotal"][0]["PayableAmount"][0]["_"] > 0
        assert inv["InvoiceTypeCode"][0]["_"] == "01" and inv["DocumentCurrencyCode"][0]["_"] == "MYR"
        assert c.get("/invoices/nope/einvoice").status_code == 404
