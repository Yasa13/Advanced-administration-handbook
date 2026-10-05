from __future__ import annotations

import csv
import hashlib
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .db import create_bank_import, insert_bank_transaction


@dataclass
class ParsedTransaction:
    booking_date: str
    value_date: str
    participant_name: str
    participant_iban: str
    booking_text: str
    purpose: str
    amount: Decimal
    currency: str
    balance: Decimal | None
    category: str
    source_row: int
    row_hash: str


def _parse_decimal(value: str) -> Decimal:
    raw = (value or "").strip().replace(" ", "")
    if not raw:
        return Decimal("0")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"Ungültiger Betrag: {value!r}") from exc


def _parse_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value[:10]


def _stable_hash(prefix: str, *parts: object) -> str:
    normalized = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(f"{prefix}|{normalized}".encode("utf-8")).hexdigest()


def parse_bank_csv(raw: bytes, filename: str) -> tuple[dict[str, str], list[ParsedTransaction]]:
    """Parse the Berliner Volksbank CSV format used by the user."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError("CSV enthält keine Kopfzeile.")

    required = {"Buchungstag", "Name Zahlungsbeteiligter", "Verwendungszweck", "Betrag", "Waehrung"}
    missing = required.difference(reader.fieldnames)
    if missing:
        raise ValueError("Nicht unterstütztes CSV-Format. Fehlende Spalten: " + ", ".join(sorted(missing)))

    txs: list[ParsedTransaction] = []
    account_meta: dict[str, str] = {}
    for index, row in enumerate(reader, start=2):
        if not account_meta:
            account_meta = {
                "account_name": (row.get("Bezeichnung Auftragskonto") or "").strip(),
                "account_iban": (row.get("IBAN Auftragskonto") or "").strip(),
                "bank_name": (row.get("Bankname Auftragskonto") or "").strip(),
                "filename": filename,
                "source_format": "CSV",
            }
        amount = _parse_decimal(row.get("Betrag", ""))
        balance_raw = (row.get("Saldo nach Buchung") or "").strip()
        balance = _parse_decimal(balance_raw) if balance_raw else None
        txs.append(
            ParsedTransaction(
                booking_date=_parse_date(row.get("Buchungstag", "")),
                value_date=_parse_date(row.get("Valutadatum", "")),
                participant_name=(row.get("Name Zahlungsbeteiligter") or "").strip(),
                participant_iban=(row.get("IBAN Zahlungsbeteiligter") or "").strip(),
                booking_text=(row.get("Buchungstext") or "").strip(),
                purpose=(row.get("Verwendungszweck") or "").strip(),
                amount=amount,
                currency=(row.get("Waehrung") or "EUR").strip() or "EUR",
                balance=balance,
                category=(row.get("Kategorie") or "").strip(),
                source_row=index,
                row_hash=_stable_hash(
                    "CSV",
                    row.get("Buchungstag", ""),
                    row.get("Valutadatum", ""),
                    row.get("Name Zahlungsbeteiligter", ""),
                    row.get("IBAN Zahlungsbeteiligter", ""),
                    row.get("Buchungstext", ""),
                    row.get("Verwendungszweck", ""),
                    row.get("Betrag", ""),
                ),
            )
        )
    return account_meta, txs


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(node: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in list(node) if _local_name(child.tag) == name]


def _child(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    for child in list(node):
        if _local_name(child.tag) == name:
            return child
    return None


def _path(node: ET.Element | None, *names: str) -> ET.Element | None:
    current = node
    for name in names:
        current = _child(current, name)
        if current is None:
            return None
    return current


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _path_text(node: ET.Element | None, *names: str) -> str:
    return _text(_path(node, *names))


def _all_desc(node: ET.Element | None, name: str) -> list[ET.Element]:
    if node is None:
        return []
    return [item for item in node.iter() if _local_name(item.tag) == name]


def _first_desc_text(node: ET.Element | None, name: str) -> str:
    items = _all_desc(node, name)
    return _text(items[0]) if items else ""


def _camt_date(node: ET.Element | None, group: str) -> str:
    parent = _child(node, group)
    if parent is None:
        return ""
    return _parse_date(_path_text(parent, "Dt") or _path_text(parent, "DtTm"))


def _camt_counterparty(tx: ET.Element | None, direction: str) -> tuple[str, str]:
    related = _child(tx, "RltdPties")
    if related is None:
        return "", ""
    if direction == "CRDT":
        party_name = _path_text(related, "Dbtr", "Nm")
        iban = _path_text(related, "DbtrAcct", "Id", "IBAN")
    else:
        party_name = _path_text(related, "Cdtr", "Nm")
        iban = _path_text(related, "CdtrAcct", "Id", "IBAN")
    if not party_name:
        party_name = _path_text(related, "UltmtDbtr", "Nm") if direction == "CRDT" else _path_text(related, "UltmtCdtr", "Nm")
    return party_name, iban


def _camt_amount(tx: ET.Element | None, entry: ET.Element) -> tuple[Decimal, str]:
    tx_amt = _path(tx, "AmtDtls", "TxAmt", "Amt")
    amount_node = tx_amt if tx_amt is not None else _child(entry, "Amt")
    amount = _parse_decimal(_text(amount_node))
    currency = (amount_node.attrib.get("Ccy", "") if amount_node is not None else "") or "EUR"
    return amount, currency


def parse_camt(raw: bytes, filename: str) -> tuple[dict[str, str], list[ParsedTransaction]]:
    """Parse common ISO 20022 CAMT.052/053/054 statement structures.

    The parser intentionally normalizes all variants into Finora's existing
    ParsedTransaction model so matching and persistence remain unchanged.
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("CAMT/XML konnte nicht gelesen werden.") from exc

    account = next(iter(_all_desc(root, "Acct")), None)
    account_meta = {
        "account_name": _path_text(account, "Nm"),
        "account_iban": _path_text(account, "Id", "IBAN"),
        "bank_name": "",
        "filename": filename,
        "source_format": "CAMT",
    }
    servicer = next(iter(_all_desc(root, "Svcr")), None)
    if servicer is not None:
        account_meta["bank_name"] = _path_text(servicer, "FinInstnId", "Nm")

    txs: list[ParsedTransaction] = []
    source_row = 0
    entries = _all_desc(root, "Ntry")
    if not entries:
        raise ValueError("Keine CAMT-Buchungen (Ntry) gefunden.")

    for entry in entries:
        direction = (_path_text(entry, "CdtDbtInd") or "CRDT").upper()
        booking_date = _camt_date(entry, "BookgDt")
        value_date = _camt_date(entry, "ValDt")
        booking_text = _path_text(entry, "AddtlNtryInf") or _first_desc_text(_child(entry, "BkTxCd"), "Cd")
        details = _all_desc(_child(entry, "NtryDtls"), "TxDtls")
        if not details:
            details = [None]

        for detail in details:
            source_row += 1
            amount, currency = _camt_amount(detail, entry)
            sign = Decimal("-1") if direction == "DBIT" else Decimal("1")
            amount *= sign
            participant_name, participant_iban = _camt_counterparty(detail, direction)
            rmt = _child(detail, "RmtInf") if detail is not None else None
            purpose_parts = [_text(item) for item in _children(rmt, "Ustrd")] if rmt is not None else []
            refs = _child(detail, "Refs") if detail is not None else None
            reference = _path_text(refs, "EndToEndId") or _path_text(refs, "AcctSvcrRef")
            if reference and reference.upper() != "NOTPROVIDED":
                purpose_parts.append(reference)
            purpose = " ".join(part for part in purpose_parts if part).strip()
            if not purpose:
                purpose = _path_text(entry, "AddtlNtryInf")
            txs.append(
                ParsedTransaction(
                    booking_date=booking_date,
                    value_date=value_date,
                    participant_name=participant_name,
                    participant_iban=participant_iban,
                    booking_text=booking_text,
                    purpose=purpose,
                    amount=amount,
                    currency=currency,
                    balance=None,
                    category="",
                    source_row=source_row,
                    row_hash=_stable_hash(
                        "CAMT",
                        account_meta["account_iban"],
                        booking_date,
                        value_date,
                        participant_name,
                        participant_iban,
                        purpose,
                        amount,
                        currency,
                        reference,
                    ),
                )
            )
    return account_meta, txs


def _decode_mt940(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="replace")


def _split_mt940_tags(text: str) -> list[tuple[str, str]]:
    tags: list[tuple[str, str]] = []
    current_tag = ""
    current_value: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        match = re.match(r"^:([0-9]{2}[A-Z]?):(.*)$", line)
        if match:
            if current_tag:
                tags.append((current_tag, "\n".join(current_value).strip()))
            current_tag = match.group(1)
            current_value = [match.group(2)]
        elif current_tag:
            current_value.append(line)
    if current_tag:
        tags.append((current_tag, "\n".join(current_value).strip()))
    return tags


def _mt940_date(yymmdd: str) -> date:
    year = 2000 + int(yymmdd[:2])
    return date(year, int(yymmdd[2:4]), int(yymmdd[4:6]))


def _mt940_value_date(booking: date, mmdd: str) -> date:
    candidate = date(booking.year, int(mmdd[:2]), int(mmdd[2:4]))
    delta = candidate - booking
    if delta.days > 183:
        candidate = date(booking.year - 1, candidate.month, candidate.day)
    elif delta.days < -183:
        candidate = date(booking.year + 1, candidate.month, candidate.day)
    return candidate


def _parse_mt940_61(value: str) -> tuple[date, date, Decimal, str, str]:
    compact = value.replace("\n", "")
    match = re.match(
        r"^(?P<booking>\d{6})(?P<value>\d{4})?(?P<dc>R?[CD])(?P<funds>[A-Z])?"
        r"(?P<amount>\d+(?:[,.]\d{0,2})?)(?P<rest>.*)$",
        compact,
    )
    if not match:
        raise ValueError(f"MT940 :61:-Zeile nicht unterstützt: {value!r}")
    booking = _mt940_date(match.group("booking"))
    value = _mt940_value_date(booking, match.group("value")) if match.group("value") else booking
    amount = _parse_decimal(match.group("amount"))
    dc = match.group("dc")
    sign = Decimal("1") if dc.endswith("C") else Decimal("-1")
    if dc.startswith("R"):
        sign *= Decimal("-1")
    amount *= sign
    rest = match.group("rest") or ""
    txn_code_match = re.search(r"N([A-Z0-9]{3})", rest)
    booking_text = txn_code_match.group(1) if txn_code_match else ""
    return booking, value, amount, booking_text, rest


def _parse_mt940_86(value: str) -> tuple[str, str, str, str]:
    fields = {key: val.strip() for key, val in re.findall(r"\?(\d{2})([^?]*)", value, flags=re.S)}
    booking_text = fields.get("00", "")
    purpose = " ".join(fields.get(f"{i:02d}", "") for i in range(20, 30)).strip()
    participant_name = " ".join(part for part in (fields.get("32", ""), fields.get("33", "")) if part).strip()
    participant_iban = ""
    field31 = re.sub(r"\s+", "", fields.get("31", "").upper())
    if re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", field31):
        participant_iban = field31
    else:
        # Search individual structured fields without concatenating field boundaries;
        # otherwise a following purpose/name can be mistaken for part of the IBAN.
        for candidate in (purpose, value):
            iban_match = re.search(r"(?<![A-Z0-9])([A-Z]{2}\d{2}[A-Z0-9]{10,30})(?![A-Z0-9])", candidate.upper())
            if iban_match:
                participant_iban = iban_match.group(1)
                break
    if not purpose:
        purpose = re.sub(r"\?\d{2}", " ", value)
        purpose = re.sub(r"\s+", " ", purpose).strip()
    return participant_name, participant_iban, booking_text, purpose


def parse_mt940(raw: bytes, filename: str) -> tuple[dict[str, str], list[ParsedTransaction]]:
    text = _decode_mt940(raw)
    tags = _split_mt940_tags(text)
    if not tags or not any(tag == "61" for tag, _ in tags):
        raise ValueError("Keine MT940-Buchungen (:61:) gefunden.")

    account_id = next((value for tag, value in tags if tag == "25"), "")
    iban_match = re.search(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", account_id.upper().replace(" ", ""))
    account_meta = {
        "account_name": "",
        "account_iban": iban_match.group(0) if iban_match else account_id.strip(),
        "bank_name": "",
        "filename": filename,
        "source_format": "MT940",
    }

    txs: list[ParsedTransaction] = []
    pending_61: str | None = None
    source_row = 0

    def flush(detail_86: str = "") -> None:
        nonlocal pending_61, source_row
        if pending_61 is None:
            return
        source_row += 1
        booking, value_date, amount, code61, rest = _parse_mt940_61(pending_61)
        participant_name, participant_iban, code86, purpose = _parse_mt940_86(detail_86)
        booking_text = code86 or code61
        txs.append(
            ParsedTransaction(
                booking_date=booking.isoformat(),
                value_date=value_date.isoformat(),
                participant_name=participant_name,
                participant_iban=participant_iban,
                booking_text=booking_text,
                purpose=purpose,
                amount=amount,
                currency="EUR",
                balance=None,
                category="",
                source_row=source_row,
                row_hash=_stable_hash(
                    "MT940",
                    account_meta["account_iban"],
                    pending_61,
                    detail_86,
                    rest,
                ),
            )
        )
        pending_61 = None

    for tag, value in tags:
        if tag == "61":
            flush()
            pending_61 = value
        elif tag == "86" and pending_61 is not None:
            flush(value)
    flush()
    return account_meta, txs


def detect_bank_format(raw: bytes, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    sample = raw[:4096].lstrip()
    if suffix == ".csv":
        return "CSV"
    if suffix in {".xml", ".camt"} or sample.startswith(b"<?xml") or b"<Document" in sample:
        return "CAMT"
    if suffix in {".sta", ".mt940", ".txt"} or sample.startswith(b":20:") or b"\n:61:" in sample:
        return "MT940"
    raise ValueError("Nicht unterstütztes Bankformat. Erlaubt: CSV, CAMT/XML oder MT940.")


def parse_bank_file(raw: bytes, filename: str) -> tuple[dict[str, str], list[ParsedTransaction]]:
    source_format = detect_bank_format(raw, filename)
    if source_format == "CSV":
        return parse_bank_csv(raw, filename)
    if source_format == "CAMT":
        return parse_camt(raw, filename)
    return parse_mt940(raw, filename)


def import_bank_file(raw: bytes, filename: str) -> dict[str, int | str]:
    meta, txs = parse_bank_file(raw, filename)
    import_id = create_bank_import(filename, meta)
    inserted = 0
    duplicates = 0
    for tx in txs:
        if insert_bank_transaction(import_id, tx):
            inserted += 1
        else:
            duplicates += 1
    return {
        "import_id": import_id,
        "inserted": inserted,
        "duplicates": duplicates,
        "account_name": meta.get("account_name", ""),
        "account_iban": meta.get("account_iban", ""),
        "bank_name": meta.get("bank_name", ""),
        "source_format": meta.get("source_format", ""),
    }


def import_bank_csv(raw: bytes, filename: str) -> dict[str, int | str]:
    """Backward-compatible wrapper retained for v0.6.2 callers/tests."""
    meta, txs = parse_bank_csv(raw, filename)
    import_id = create_bank_import(filename, meta)
    inserted = 0
    duplicates = 0
    for tx in txs:
        if insert_bank_transaction(import_id, tx):
            inserted += 1
        else:
            duplicates += 1
    return {
        "import_id": import_id,
        "inserted": inserted,
        "duplicates": duplicates,
        "account_name": meta.get("account_name", ""),
        "account_iban": meta.get("account_iban", ""),
        "bank_name": meta.get("bank_name", ""),
        "source_format": "CSV",
    }
