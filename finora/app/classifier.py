import re
from datetime import datetime
from pathlib import Path
from .models import Classification
from .learning import predict_from_history

ADDRESSEE_RULES = {
    "PSS": [
        "paletten-service-schlemeier",
        "paletten service schlemeier",
        "palettenservice schlemeier",
        "schlemeier",
        "pss",
    ],
    "PSSpandau": [
        "paletten-service-spandau",
        "paletten service spandau",
        "palettenservice spandau",
        "psspandau",
    ],
    "BP": ["berliner paletten"],
}

PRIVATE_PEOPLE = {
    "Yasmin": ["yasmin", "yasa"],
    "Frank": ["frank"],
    "Marina": ["marina"],
    "Karl": ["karl"],
}

DOC_RULES = {
    "Steuerbescheid": ["finanzamt", "steuerbescheid", "vorauszahlung", "steuerfestsetzung"],
    "Kontoauszug": ["kontoauszug", "kontostand", "saldo", "auszugsnummer"],
    "Lieferschein": ["lieferschein", "lieferscheinnummer", "lieferdatum"],
    "Bankbeleg": ["girocard", "sepa", "ueberweisung", "überweisung", "verwendungszweck", "buchungstag"],
    "Kassenbeleg": ["kassenbon", "bar", "rueckgeld", "rückgeld", "gegeben"],
    "Eingangsrechnung": ["rechnung", "rechnungsnummer", "netto", "brutto", "zahlbar bis"],
    "Mahnung": ["mahnung", "mahnstufe", "zahlungsaufforderung"],
    "Zahlungsavis": ["zahlungsavis", "avis", "zahlungsmitteilung"],
    "Zahlungsnachweis": ["zahlungsnachweis", "zahlungsbestaetigung", "zahlungsbestätigung"],
    "Vertrag": ["vertrag", "vereinbarung", "laufzeit", "kuendigung", "kündigung"],
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _score_hits(text: str, terms: list[str]) -> tuple[int, list[str]]:
    hits = [t for t in terms if t in text]
    return len(hits), hits


def detect_addressee(text: str) -> tuple[str, str, str, float]:
    """Return addressee_type, addressee_name, private_person, confidence."""
    n = _norm(text)
    best_type, best_name, best_private, best_conf = "Unklar", "", "", 0.0

    for key, aliases in ADDRESSEE_RULES.items():
        score, _ = _score_hits(n, aliases)
        # Avoid weak acronym-only classification.
        if key == "PSS" and score == 1 and re.search(r"\bpss\b", n) and "schlemeier" not in n:
            score = 0
        confidence = min(0.98, 0.55 + score * 0.15) if score else 0.0
        if confidence > best_conf:
            full = {
                "PSS": "Paletten-Service-Schlemeier",
                "PSSpandau": "Paletten-Service-Spandau",
                "BP": "Berliner Paletten",
            }[key]
            best_type, best_name, best_private, best_conf = key, full, "", confidence

    # Private-person detection is deliberately weaker than exact company matches.
    if best_conf == 0.0:
        for person, aliases in PRIVATE_PEOPLE.items():
            if any(re.search(rf"\b{re.escape(alias)}\b", n) for alias in aliases):
                return "Privat", person, person, 0.72

    return best_type, best_name, best_private, best_conf


def detect_document_type(text: str) -> tuple[str, float]:
    n = _norm(text)
    best_type, best_score = "Sonstiges", 0
    for doc_type, terms in DOC_RULES.items():
        score, _ = _score_hits(n, terms)
        if score > best_score:
            best_type, best_score = doc_type, score
    confidence = min(0.97, 0.50 + best_score * 0.1) if best_score else 0.2
    return best_type, confidence


def detect_date(text: str) -> str:
    m = re.search(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b", text)
    if not m:
        return ""
    d, mo, y = map(int, m.groups())
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return ""


def _normalize_german_amount(raw: str) -> str:
    """Normalize OCR amount text to German display format, e.g. 1.399,44.

    Supports common OCR variants such as 1.399,44, 1 399,44, 1399,44 and
    1,399.44. The returned string always uses a comma as decimal separator
    and a dot as thousands separator.
    """
    value = re.sub(r"\s+", "", raw.strip())
    if not value:
        return ""

    # Determine the decimal separator from the final two digits.
    m = re.search(r"([.,])(\d{2})$", value)
    if not m:
        return ""
    dec_sep = m.group(1)
    cents = m.group(2)
    integer = value[: m.start(1)]

    # Remove all thousands separators from the integer part.
    integer_digits = re.sub(r"[^0-9]", "", integer)
    if not integer_digits:
        return ""

    # Re-add German thousands separators for display consistency.
    groups = []
    while integer_digits:
        groups.append(integer_digits[-3:])
        integer_digits = integer_digits[:-3]
    integer_formatted = ".".join(reversed(groups))
    return f"{integer_formatted},{cents}"


def detect_amount(text: str) -> str:
    """Detect the most likely gross/total amount from OCR text.

    Prefer amounts occurring close to strong total labels (Gesamtbetrag,
    Brutto, Endbetrag, Summe). Fall back to the last monetary amount.
    Thousands separators are preserved and normalized.
    """
    # German and international OCR variants: 1.399,44 / 1 399,44 / 1399,44 / 1,399.44
    amount_pattern = r"(?<!\d)(?:\d{1,3}(?:[.\s]\d{3})+|\d{1,7}|\d{1,3}(?:,\d{3})+)[,.]\d{2}(?!\d)"

    label_patterns = [
        r"gesamtbetrag",
        r"rechnungsbetrag",
        r"endbetrag",
        r"zahlbetrag",
        r"gesamt(?:summe)?",
        r"brutto(?:betrag)?",
        r"summe",
    ]

    # Search line-by-line first because invoices usually place the label and value together.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for label in label_patterns:
        rx_label = re.compile(label, re.I)
        for i, line in enumerate(lines):
            if not rx_label.search(line):
                continue

            # First prefer an amount on the same line as the total label.
            same_line = re.findall(amount_pattern, line)
            if same_line:
                return _normalize_german_amount(same_line[-1])

            # Some OCR layouts put the amount on the immediately following line.
            if i + 1 < len(lines):
                next_line = re.findall(amount_pattern, lines[i + 1])
                if next_line:
                    return _normalize_german_amount(next_line[0])

    candidates = re.findall(amount_pattern, text)
    if not candidates:
        return ""
    return _normalize_german_amount(candidates[-1])


def detect_invoice_number(text: str) -> str:
    patterns = [
        r"(?:rechnungs(?:nummer|nr\.?|nummer\s*:)|rechnung\s*nr\.?)[\s:#-]*([A-Z0-9\-/]+)",
        r"\b(RE[-_/]?\d+[A-Z0-9\-/]*)\b",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(1)
    return ""


def _safe_component(value: str, fallback: str = "Unklar") -> str:
    replacements = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})
    value = (value or fallback).translate(replacements)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    return safe or fallback


def build_entity_root(addressee_type: str, private_person: str = "") -> str:
    mapping = {
        "PSS": "PSS",
        "BP": "Berliner-Paletten",
        "PSSpandau": "Paletten-Service-Spandau",
    }
    if addressee_type == "Privat":
        return f"Privat/{_safe_component(private_person, 'Unklar')}"
    return mapping.get(addressee_type, "Unklar")


def build_target_folder(
    doc_type: str,
    date: str,
    correspondent: str,
    addressee_type: str = "Unklar",
    private_person: str = "",
) -> str:
    year = date[:4] if date else "Unbekannt"
    month = date[5:7] if len(date) >= 7 else "00"
    corr = _safe_component(correspondent, "Unklar")
    entity = build_entity_root(addressee_type, private_person)

    mapping = {
        "Eingangsrechnung": f"{entity}/Buchhaltung/Eingangsrechnungen/{year}/{corr}",
        "Ausgangsrechnung": f"{entity}/Buchhaltung/Ausgangsrechnungen/{year}/{corr}",
        "Eingehende Gutschrift": f"{entity}/Buchhaltung/Eingangsrechnungen/{year}/{corr}",
        "Ausgehende Gutschrift": f"{entity}/Buchhaltung/Ausgangsrechnungen/{year}/{corr}",
        "Kassenbeleg": f"{entity}/Buchhaltung/Kassenbelege/{year}/{month}",
        "Bankbeleg": f"{entity}/Buchhaltung/Bankbelege/{year}/{month}",
        "Kontoauszug": f"{entity}/Buchhaltung/Kontoauszuege/{year}/{corr}",
        "Steuerbescheid": f"{entity}/Buchhaltung/Steuerbescheide/{year}/{corr}",
        "Mahnung": f"{entity}/Buchhaltung/Mahnungen/{year}/{corr}",
        "Zahlungsavis": f"{entity}/Buchhaltung/Zahlungen/{year}/{corr}",
        "Zahlungsnachweis": f"{entity}/Buchhaltung/Zahlungen/{year}/{corr}",
        "Lieferschein": f"{entity}/Lieferscheine/{year}/{corr}",
        "Vertrag": f"{entity}/Vertraege/{year}/{corr}",
    }
    return mapping.get(doc_type, f"{entity}/Sonstiges/{year}")


def classify(text: str, original_name: str) -> Classification:
    doc_type, doc_conf = detect_document_type(text)
    add_type, add_name, private_person, add_conf = detect_addressee(text)
    date = detect_date(text)
    amount = detect_amount(text)
    inv = detect_invoice_number(text)
    correspondent = "Unklar"
    corr_conf = 0.1
    learned_from_history = False
    learning_note = ""

    learned = predict_from_history(text)
    # Historical suggestions only replace the base rule when they are stronger.
    if learned.document_type and learned.confidence_document_type > doc_conf:
        doc_type = learned.document_type
        doc_conf = learned.confidence_document_type
        learned_from_history = True
    if learned.correspondent and learned.confidence_correspondent > corr_conf:
        correspondent = learned.correspondent
        corr_conf = learned.confidence_correspondent
        learned_from_history = True
    if learned.addressee_type and learned.confidence_addressee > add_conf:
        add_type = learned.addressee_type
        add_conf = learned.confidence_addressee
        if add_type == "PSS":
            add_name = "Paletten-Service-Schlemeier"
        elif add_type == "PSSpandau":
            add_name = "Paletten-Service-Spandau"
        elif add_type == "BP":
            add_name = "Berliner Paletten"
        learned_from_history = True
    if add_type == "Privat" and learned.private_person and learned.confidence_private_person >= 0.55:
        private_person = learned.private_person
        add_name = learned.private_person
        learned_from_history = True

    if learned_from_history:
        learning_note = learned.reason

    title = Path(original_name).stem
    target = build_target_folder(doc_type, date, correspondent, add_type, private_person)
    return Classification(
        document_type=doc_type,
        correspondent=correspondent,
        addressee_type=add_type,
        addressee_name=add_name,
        private_person=private_person,
        document_date=date,
        invoice_number=inv,
        gross_amount=amount,
        title=title,
        target_folder=target,
        confidence_document_type=doc_conf,
        confidence_correspondent=corr_conf,
        confidence_addressee=add_conf,
        learned_from_history=learned_from_history,
        learning_note=learning_note,
    )
