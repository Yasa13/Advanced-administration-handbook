from app import learning


def test_similarity_ignores_changing_numbers():
    a = "Shell GmbH Rechnung 4711 Diesel Gesamt 120,00 EUR Berlin"
    b = "Shell GmbH Rechnung 9922 Diesel Gesamt 345,90 EUR Berlin"
    assert learning.similarity(a, b) > 0.45


def test_repeated_history_raises_confidence(monkeypatch):
    rows = [
        {
            "ocr_text": f"Shell Tankstelle Berlin Diesel Beleg Nummer {i} Fahrzeug",
            "document_type": "Eingangsrechnung",
            "correspondent": "Shell",
            "addressee_type": "PSS",
            "private_person": "",
            "document_type_weight": 1.0,
            "correspondent_weight": 1.0,
            "addressee_type_weight": 1.0,
            "private_person_weight": 1.0,
        }
        for i in range(5)
    ]
    monkeypatch.setattr(learning, "get_learning_documents", lambda limit=500: rows)
    result = learning.predict_from_history("Shell Tankstelle Berlin Diesel Beleg Nummer 999 Fahrzeug")
    assert result.correspondent == "Shell"
    assert result.addressee_type == "PSS"
    assert result.confidence_correspondent >= 0.85


def test_correction_weight_can_break_tie(monkeypatch):
    rows = [
        {
            "ocr_text": "Muster Lieferant Berlin Paletten Lieferung",
            "document_type": "Eingangsrechnung",
            "correspondent": "Falsch GmbH",
            "addressee_type": "PSS",
            "private_person": "",
            "document_type_weight": 1.0,
            "correspondent_weight": 1.0,
            "addressee_type_weight": 1.0,
            "private_person_weight": 1.0,
        },
        {
            "ocr_text": "Muster Lieferant Berlin Paletten Lieferung",
            "document_type": "Eingangsrechnung",
            "correspondent": "Richtig GmbH",
            "addressee_type": "PSS",
            "private_person": "",
            "document_type_weight": 1.0,
            "correspondent_weight": 1.35,
            "addressee_type_weight": 1.0,
            "private_person_weight": 1.0,
        },
    ]
    monkeypatch.setattr(learning, "get_learning_documents", lambda limit=500: rows)
    result = learning.predict_from_history("Muster Lieferant Berlin Paletten Lieferung")
    assert result.correspondent == "Richtig GmbH"
