from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .db import get_learning_documents

# Generic invoice vocabulary is ignored so recurring supplier/customer wording
# carries more weight than words found on almost every commercial document.
STOPWORDS = {
    "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
    "eines", "mit", "von", "vom", "fuer", "für", "auf", "aus", "bei", "zur", "zum",
    "rechnung", "rechnungsnummer", "datum", "netto", "brutto", "gesamt", "summe",
    "mwst", "ust", "eur", "euro", "seite", "betrag", "zahlbar", "lieferung",
}


@dataclass
class LearnedSuggestion:
    document_type: str = ""
    correspondent: str = ""
    addressee_type: str = ""
    private_person: str = ""
    confidence_document_type: float = 0.0
    confidence_correspondent: float = 0.0
    confidence_addressee: float = 0.0
    confidence_private_person: float = 0.0
    reason: str = ""


def normalize_for_similarity(text: str) -> set[str]:
    text = text.lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    # Dates, invoice numbers and amounts usually change between otherwise identical documents.
    text = re.sub(r"\b\d+[\d.,:/-]*\b", " <num> ", text)
    tokens = re.findall(r"[a-z][a-z0-9-]{2,}", text)
    return {token for token in tokens if token not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    ta, tb = normalize_for_similarity(a), normalize_for_similarity(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _vote(rows: list[tuple[dict, float]], field: str) -> tuple[str, float, int, float]:
    votes: dict[str, float] = defaultdict(float)
    supports: dict[str, int] = defaultdict(int)
    sims: dict[str, list[float]] = defaultdict(list)
    weight_field = f"{field}_weight"

    for row, sim in rows:
        value = (row.get(field) or "").strip()
        if not value or value == "Unklar":
            continue
        # A user correction is stored with a higher weight than a simple confirmation.
        training_weight = float(row.get(weight_field, 1.0) or 1.0)
        votes[value] += sim * training_weight
        supports[value] += 1
        sims[value].append(sim)

    if not votes:
        return "", 0.0, 0, 0.0

    best = max(votes, key=votes.get)
    total = sum(votes.values()) or 1.0
    share = votes[best] / total
    support = supports[best]
    avg_sim = sum(sims[best]) / len(sims[best])

    # Repetition deliberately raises confidence slowly. One example remains weak,
    # three become useful, five or more may become a very strong suggestion.
    support_bonus = min(0.20, max(0, support - 1) * 0.05)
    raw = 0.45 * avg_sim + 0.35 * share + support_bonus
    cap = 0.68 if support == 1 else 0.78 if support == 2 else 0.88 if support < 5 else 0.96
    return best, min(cap, raw), support, avg_sim


def predict_from_history(text: str) -> LearnedSuggestion:
    history = get_learning_documents(limit=500)
    scored: list[tuple[dict, float]] = []
    for row in history:
        sim = similarity(text, row.get("ocr_text", ""))
        if sim >= 0.22:
            scored.append((row, sim))

    scored.sort(key=lambda item: item[1], reverse=True)
    scored = scored[:20]
    if not scored:
        return LearnedSuggestion()

    dt, dtc, dtn, dts = _vote(scored, "document_type")
    corr, corrc, corrn, corrs = _vote(scored, "correspondent")
    addr, addrc, addrn, addrs = _vote(scored, "addressee_type")
    person, personc, personn, persons = _vote(scored, "private_person")

    strongest_support = max(dtn, corrn, addrn, personn)
    strongest_sim = max(dts, corrs, addrs, persons)
    reason = ""
    if strongest_support:
        reason = (
            f"Aus {strongest_support} aehnlichen bestaetigten Beleg(en) gelernt; "
            f"Aehnlichkeit bis {strongest_sim:.0%}."
        )

    return LearnedSuggestion(
        document_type=dt,
        correspondent=corr,
        addressee_type=addr,
        private_person=person,
        confidence_document_type=dtc,
        confidence_correspondent=corrc,
        confidence_addressee=addrc,
        confidence_private_person=personc,
        reason=reason,
    )
