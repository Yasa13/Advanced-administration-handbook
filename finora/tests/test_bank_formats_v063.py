from decimal import Decimal

from app.bank import detect_bank_format, parse_bank_file, parse_camt, parse_mt940


def test_parse_camt053_credit_transaction():
    raw = b'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08">
  <BkToCstmrStmt><Stmt>
    <Acct><Id><IBAN>DE11111111111111111111</IBAN></Id><Nm>PSS Geschaeft</Nm>
      <Svcr><FinInstnId><Nm>Testbank</Nm></FinInstnId></Svcr></Acct>
    <Ntry>
      <Amt Ccy="EUR">799.68</Amt><CdtDbtInd>CRDT</CdtDbtInd>
      <BookgDt><Dt>2026-10-05</Dt></BookgDt><ValDt><Dt>2026-10-05</Dt></ValDt>
      <NtryDtls><TxDtls>
        <Refs><EndToEndId>RG-2026-0184</EndToEndId></Refs>
        <RltdPties><Dbtr><Nm>Kunde GmbH</Nm></Dbtr><DbtrAcct><Id><IBAN>DE22222222222222222222</IBAN></Id></DbtrAcct></RltdPties>
        <RmtInf><Ustrd>Zahlung Rechnung RG-2026-0184</Ustrd></RmtInf>
      </TxDtls></NtryDtls>
    </Ntry>
  </Stmt></BkToCstmrStmt>
</Document>'''
    meta, txs = parse_camt(raw, "camt053.xml")
    assert meta["source_format"] == "CAMT"
    assert meta["account_iban"] == "DE11111111111111111111"
    assert meta["bank_name"] == "Testbank"
    assert len(txs) == 1
    tx = txs[0]
    assert tx.amount == Decimal("799.68")
    assert tx.participant_name == "Kunde GmbH"
    assert tx.participant_iban == "DE22222222222222222222"
    assert "RG-2026-0184" in tx.purpose


def test_parse_camt_debit_is_negative():
    raw = b'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"><BkToCstmrStmt><Stmt>
<Acct><Id><IBAN>DE11111111111111111111</IBAN></Id></Acct>
<Ntry><Amt Ccy="EUR">49.99</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-10-05</Dt></BookgDt>
<NtryDtls><TxDtls><RltdPties><Cdtr><Nm>Lieferant GmbH</Nm></Cdtr></RltdPties><RmtInf><Ustrd>RE-55</Ustrd></RmtInf></TxDtls></NtryDtls>
</Ntry></Stmt></BkToCstmrStmt></Document>'''
    _, txs = parse_camt(raw, "camt.xml")
    assert txs[0].amount == Decimal("-49.99")
    assert txs[0].participant_name == "Lieferant GmbH"


def test_parse_mt940_credit_and_structured_86():
    raw = b''':20:STARTUMSE\n:25:DE11111111111111111111\n:28C:00001/001\n:60F:C261004EUR1000,00\n:61:2610051005C799,68NTRFNONREF\n:86:166?00UEBERWEISUNG?20Zahlung RG-2026-0184?31DE22222222222222222222?32Kunde GmbH\n:62F:C261005EUR1799,68\n'''
    meta, txs = parse_mt940(raw, "umsatz.mt940")
    assert meta["source_format"] == "MT940"
    assert meta["account_iban"] == "DE11111111111111111111"
    assert len(txs) == 1
    tx = txs[0]
    assert tx.booking_date == "2026-10-05"
    assert tx.value_date == "2026-10-05"
    assert tx.amount == Decimal("799.68")
    assert tx.participant_name == "Kunde GmbH"
    assert tx.participant_iban == "DE22222222222222222222"
    assert "RG-2026-0184" in tx.purpose


def test_parse_mt940_debit_is_negative():
    raw = b''':20:X\n:25:DE11111111111111111111\n:61:2610051005D49,99NTRFNONREF\n:86:166?00LASTSCHRIFT?20RE-55?32Lieferant GmbH\n'''
    _, txs = parse_mt940(raw, "umsatz.sta")
    assert txs[0].amount == Decimal("-49.99")
    assert txs[0].participant_name == "Lieferant GmbH"


def test_format_detection_and_dispatch():
    csv_raw = b"Buchungstag;Name Zahlungsbeteiligter;Verwendungszweck;Betrag;Waehrung\n05.10.2026;Kunde;RG-1;10,00;EUR\n"
    assert detect_bank_format(csv_raw, "x.csv") == "CSV"
    meta, txs = parse_bank_file(csv_raw, "x.csv")
    assert meta["source_format"] == "CSV"
    assert txs[0].amount == Decimal("10.00")
