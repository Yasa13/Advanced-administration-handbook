from app.classifier import build_target_folder, detect_addressee, detect_document_type


def test_pss():
    result = detect_addressee("Rechnung an Paletten-Service-Schlemeier")
    assert result[0] == "PSS"


def test_pss_spandau():
    result = detect_addressee("Empfaenger Paletten-Service-Spandau")
    assert result[0] == "PSSpandau"


def test_bp():
    result = detect_addressee("Berliner Paletten Rechnung")
    assert result[0] == "BP"


def test_private_yasmin():
    result = detect_addressee("Rechnung an Yasmin")
    assert result[0] == "Privat"
    assert result[2] == "Yasmin"


def test_tax_notice():
    assert detect_document_type("Finanzamt Steuerbescheid Umsatzsteuer Vorauszahlung")[0] == "Steuerbescheid"


def test_pss_lieferschein_target():
    target = build_target_folder("Lieferschein", "2026-08-18", "Leergut Nord GmbH", "PSS", "")
    assert target == "PSS/Lieferscheine/2026/Leergut-Nord-GmbH"


def test_private_tax_target():
    target = build_target_folder("Steuerbescheid", "2026-08-18", "Finanzamt", "Privat", "Yasmin")
    assert target == "Privat/Yasmin/Buchhaltung/Steuerbescheide/2026/Finanzamt"


def test_removed_document_types_are_not_detected():
    assert detect_document_type("abliefernachweis frachtpapier")[0] == "Sonstiges"


def test_amount_with_german_thousands_separator():
    from app.classifier import detect_amount
    text = "Netto 1.175,99 EUR\nMwSt 223,45 EUR\nGesamtbetrag 1.399,44 EUR"
    assert detect_amount(text) == "1.399,44"


def test_amount_with_space_thousands_separator():
    from app.classifier import detect_amount
    text = "Bruttobetrag 1 399,44 EUR"
    assert detect_amount(text) == "1.399,44"


def test_amount_without_thousands_separator():
    from app.classifier import detect_amount
    text = "Gesamtsumme 1399,44 EUR"
    assert detect_amount(text) == "1.399,44"


def test_amount_prefers_total_label():
    from app.classifier import detect_amount
    text = "Position 399,44 EUR\nNetto 1.175,99 EUR\nGesamtbetrag 1.399,44 EUR\nRabatt 10,00 EUR"
    assert detect_amount(text) == "1.399,44"
