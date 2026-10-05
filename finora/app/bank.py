from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

from .bank_import import (
    ParsedTransaction,
    detect_bank_format,
    import_bank_csv,
    import_bank_file,
    parse_bank_csv,
    parse_bank_file,
    parse_camt,
    parse_mt940,
)
from .db import get_open_invoice_candidates, list_bank_transactions

def _norm(value: str) -> str:
    value = (value or "").lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", value)


def _to_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    raw = str(value).strip()
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def score_candidate(tx: dict, candidate: dict, amount_override: object | None = None) -> tuple[float, list[str]]:
    amount = abs(_to_decimal(amount_override if amount_override is not None else tx.get("remaining_amount", tx.get("amount"))))
    open_amount = abs(_to_decimal(candidate.get("open_amount") or candidate.get("gross_amount")))
    purpose = _norm((tx.get("purpose") or "") + " " + (tx.get("booking_text") or ""))
    participant = _norm(tx.get("participant_name") or "")
    invoice_number = _norm(candidate.get("invoice_number") or "")
    correspondent = _norm(candidate.get("correspondent") or "")

    score = 0.0
    reasons: list[str] = []

    if open_amount > 0 and amount > 0:
        diff = abs(amount - open_amount)
        if diff <= Decimal("0.01"):
            score += 0.55
            reasons.append("Betrag stimmt exakt")
        elif amount < open_amount:
            ratio = amount / open_amount
            if ratio >= Decimal("0.2"):
                score += 0.25
                reasons.append("mögliche Teilzahlung")
        elif amount > open_amount:
            score += 0.18
            reasons.append("Sammelzahlung kann Rechnung abdecken")
        elif diff <= Decimal("2.00"):
            score += 0.20
            reasons.append("Betrag fast identisch")

    if invoice_number and len(invoice_number) >= 3 and invoice_number in purpose:
        score += 0.30
        reasons.append("Rechnungsnummer im Verwendungszweck")

    if correspondent and len(correspondent) >= 4:
        if correspondent in participant or correspondent in purpose:
            score += 0.15
            reasons.append("Name des Geschäftspartners passt")
        else:
            tokens = [t for t in re.split(r"[^a-z0-9]+", (candidate.get("correspondent") or "").lower()) if len(t) >= 4]
            if any(_norm(t) in participant for t in tokens):
                score += 0.08
                reasons.append("Teil des Geschäftspartnernamens passt")

    doc_type = candidate.get("document_type") or ""
    sign_ok = (tx.get("amount", 0) >= 0 and doc_type == "Ausgangsrechnung") or (
        tx.get("amount", 0) < 0 and doc_type == "Eingangsrechnung"
    )
    if sign_ok:
        score += 0.05
        reasons.append("Zahlungsrichtung passt")

    return min(score, 0.99), reasons


def _direction_ok(tx: dict, candidate: dict) -> bool:
    return (tx["amount"] >= 0 and candidate["document_type"] == "Ausgangsrechnung") or (
        tx["amount"] < 0 and candidate["document_type"] == "Eingangsrechnung"
    )


def _search_score(query: str, candidate: dict) -> tuple[int, list[str]]:
    q = _norm(query)
    if not q:
        return 0, []
    fields = {
        "Rechnungsnummer": candidate.get("invoice_number") or "",
        "Geschäftspartner": candidate.get("correspondent") or "",
        "Titel": candidate.get("title") or "",
        "Dateiname": candidate.get("original_filename") or candidate.get("stored_filename") or "",
    }
    score = 0
    reasons: list[str] = []
    for label, value in fields.items():
        n = _norm(value)
        if not n:
            continue
        if q == n:
            score += 100
            reasons.append(f"{label} exakt")
        elif q in n or n in q:
            score += 60
            reasons.append(f"{label} enthält Suche")
        else:
            tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) >= 3]
            hits = sum(1 for t in tokens if _norm(t) in n)
            if hits:
                score += 15 * hits
                reasons.append(f"{label}: {hits} Suchbegriff(e)")
    return score, reasons


def search_open_invoices(tx: dict, query: str, limit: int = 10) -> list[dict]:
    results: list[tuple[int, float, dict, list[str]]] = []
    for candidate in get_open_invoice_candidates():
        if not _direction_ok(tx, candidate):
            continue
        text_score, text_reasons = _search_score(query, candidate)
        if text_score <= 0:
            continue
        match_score, match_reasons = score_candidate(tx, candidate)
        results.append((text_score, match_score, candidate, text_reasons + match_reasons))
    results.sort(key=lambda row: (row[0], row[1]), reverse=True)
    output = []
    for text_score, match_score, candidate, reasons in results[:limit]:
        item = dict(candidate)
        item["manual_score"] = text_score
        item["match_score"] = match_score
        item["reasons"] = reasons
        output.append(item)
    return output


def attach_match_suggestions(
    transactions: Iterable[dict],
    *,
    search_tx_id: int | None = None,
    search_query: str = "",
) -> list[dict]:
    candidates = get_open_invoice_candidates()
    output: list[dict] = []
    for tx in transactions:
        item = dict(tx)
        remaining = float(item.get("remaining_amount") or 0.0)
        scored: list[tuple[float, dict, list[str]]] = []
        if remaining > 0.005:
            for candidate in candidates:
                if not _direction_ok(tx, candidate):
                    continue
                score, reasons = score_candidate(tx, candidate, amount_override=remaining)
                if score >= 0.20:
                    scored.append((score, candidate, reasons))
        scored.sort(key=lambda x: x[0], reverse=True)
        item["suggestions"] = [
            {"candidate": candidate, "score": score, "reasons": reasons}
            for score, candidate, reasons in scored[:5]
        ]
        if scored:
            best_score, best, reasons = scored[0]
            item["suggestion"] = best
            item["suggestion_score"] = best_score
            item["suggestion_reasons"] = reasons
        else:
            item["suggestion"] = None
            item["suggestion_score"] = 0.0
            item["suggestion_reasons"] = []
        if search_tx_id == int(tx["id"]) and search_query.strip():
            item["manual_query"] = search_query
            item["manual_results"] = search_open_invoices(item, search_query)
        else:
            item["manual_query"] = ""
            item["manual_results"] = []
        output.append(item)
    return output


def bank_overview(
    limit: int = 250,
    *,
    search_tx_id: int | None = None,
    search_query: str = "",
) -> list[dict]:
    return attach_match_suggestions(
        list_bank_transactions(limit=limit),
        search_tx_id=search_tx_id,
        search_query=search_query,
    )
