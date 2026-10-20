"""Builds a MyInvois (LHDN) e-invoice document, UBL 2.1 JSON, version 1.1, from an invoice in the ledger.

This produces the document. It does not submit it. Submitting needs the owner's own MyInvois taxpayer credentials,
which are not configured, so every document here has the status "ready_to_submit" and no LHDN identifier.
The company tax numbers are placeholders for the fictional business and must be replaced before a real submission.
"""
from datetime import datetime, time, timezone

from helm.models import Customer, Invoice

SELLER = {"name": "Warisan Printing Sdn Bhd", "tin": "C00000000000", "brn": "202001000001", "msic": "18110", "msic_desc": "Printing",
          "address": "Lot 12, Jalan Perindustrian 3, 41200 Klang, Selangor", "state": "12", "country": "MYS", "phone": "+60300000000"}
BUYER_TIN_PLACEHOLDER = "C00000000001"
TAX_RATE = 0.0  # printing services sold B2B are modelled here as not taxable, adjust to the real SST position before submitting
CURRENCY = "MYR"


def _party(name: str, tin: str, brn: str, address: str, state: str, phone: str, msic: str | None = None, desc: str | None = None) -> dict:
    p = {
        "Party": [{
            "IndustryClassificationCode": [{"_": msic or "00000", "name": desc or "Not applicable"}],
            "PartyIdentification": [{"ID": [{"_": tin, "schemeID": "TIN"}]}, {"ID": [{"_": brn, "schemeID": "BRN"}]}],
            "PostalAddress": [{"AddressLine": [{"Line": [{"_": address}]}], "CityName": [{"_": address.split(",")[-2].strip() if address.count(",") > 1 else "Kuala Lumpur"}],
                               "CountrySubentityCode": [{"_": state}], "Country": [{"IdentificationCode": [{"_": "MYS", "listID": "ISO3166-1", "listAgencyID": "6"}]}]}],
            "PartyLegalEntity": [{"RegistrationName": [{"_": name}]}],
            "Contact": [{"Telephone": [{"_": phone}]}],
        }]
    }
    return p


def build(invoice: Invoice, customer: Customer) -> dict:
    issued = datetime.combine(invoice.issued, time(0, 0), tzinfo=timezone.utc)
    net = round(invoice.amount / (1 + TAX_RATE), 2)
    tax = round(invoice.amount - net, 2)
    doc = {
        "_D": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "_A": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "_B": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "Invoice": [{
            "ID": [{"_": invoice.number}],
            "IssueDate": [{"_": invoice.issued.isoformat()}],
            "IssueTime": [{"_": issued.strftime("%H:%M:%SZ")}],
            "InvoiceTypeCode": [{"_": "01", "listVersionID": "1.1"}],
            "DocumentCurrencyCode": [{"_": CURRENCY}],
            "PaymentMeans": [{"PaymentMeansCode": [{"_": "03"}]}],
            "PaymentTerms": [{"Note": [{"_": f"Payment due {invoice.due.isoformat()}"}]}],
            "AccountingSupplierParty": [_party(SELLER["name"], SELLER["tin"], SELLER["brn"], SELLER["address"], SELLER["state"], SELLER["phone"], SELLER["msic"], SELLER["msic_desc"])],
            "AccountingCustomerParty": [_party(customer.name, BUYER_TIN_PLACEHOLDER, "000000000000", "Kuala Lumpur, Kuala Lumpur, Malaysia", "14", "+60300000001")],
            "TaxTotal": [{"TaxAmount": [{"_": tax, "currencyID": CURRENCY}],
                          "TaxSubtotal": [{"TaxableAmount": [{"_": net, "currencyID": CURRENCY}], "TaxAmount": [{"_": tax, "currencyID": CURRENCY}],
                                           "TaxCategory": [{"ID": [{"_": "E"}], "TaxScheme": [{"ID": [{"_": "OTH", "schemeID": "UN/ECE 5153", "schemeAgencyID": "6"}]}]}]}]}],
            "LegalMonetaryTotal": [{"LineExtensionAmount": [{"_": net, "currencyID": CURRENCY}], "TaxExclusiveAmount": [{"_": net, "currencyID": CURRENCY}],
                                    "TaxInclusiveAmount": [{"_": invoice.amount, "currencyID": CURRENCY}], "PayableAmount": [{"_": invoice.amount, "currencyID": CURRENCY}]}],
            "InvoiceLine": [{"ID": [{"_": "1"}], "InvoicedQuantity": [{"_": 1, "unitCode": "C62"}], "LineExtensionAmount": [{"_": net, "currencyID": CURRENCY}],
                             "Item": [{"CommodityClassification": [{"ItemClassificationCode": [{"_": "004", "listID": "CLASS"}]}], "Description": [{"_": f"Printing services, invoice {invoice.number}"}]}],
                             "Price": [{"PriceAmount": [{"_": net, "currencyID": CURRENCY}]}], "ItemPriceExtension": [{"Amount": [{"_": net, "currencyID": CURRENCY}]}]}],
        }],
    }
    return doc


def status(invoice: Invoice) -> str:
    return "ready_to_submit"
