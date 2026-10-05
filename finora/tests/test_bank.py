from decimal import Decimal

from app.bank import parse_bank_csv, score_candidate


def test_parse_berliner_volksbank_csv():
    raw = ("Bezeichnung Auftragskonto;IBAN Auftragskonto;BIC Auftragskonto;Bankname Auftragskonto;Buchungstag;Valutadatum;Name Zahlungsbeteiligter;IBAN Zahlungsbeteiligter;BIC (SWIFT-Code) Zahlungsbeteiligter;Buchungstext;Verwendungszweck;Betrag;Waehrung;Saldo nach Buchung;Bemerkung;Kategorie;Gekennzeichneter Umsatz;Glaeubiger ID;Mandatsreferenz\n"
           "Geschaeft;DE123;BIC;BANK;30.12.2024;30.12.2024;Kunde GmbH;;;GUTSCHRIFT;RG 2026-0184;799,68;EUR;1333,24;;Sonstiges;;;\n").encode("utf-8")
    meta, txs = parse_bank_csv(raw, "test.csv")
    assert meta["account_iban"] == "DE123"
    assert len(txs) == 1
    assert txs[0].amount == Decimal("799.68")
    assert txs[0].booking_date == "2024-12-30"


def test_score_exact_amount_and_invoice_number():
    tx = {"amount": 799.68, "purpose": "Zahlung RG 2026-0184", "booking_text": "GUTSCHRIFT", "participant_name": "Kunde GmbH"}
    candidate = {"open_amount": 799.68, "gross_amount": "799,68", "invoice_number": "2026-0184", "correspondent": "Kunde GmbH", "document_type": "Ausgangsrechnung"}
    score, reasons = score_candidate(tx, candidate)
    assert score >= 0.9
    assert any("Betrag" in reason for reason in reasons)
