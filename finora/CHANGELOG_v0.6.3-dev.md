# Finora v0.6.3-dev

Entwicklungsstand auf Basis von v0.6.2.

## Neu
- Bankimport in separates Modul `app/bank_import.py` ausgelagert.
- Einheitliche interne Transaktionsstruktur für CSV, CAMT und MT940.
- Format-Erkennung und gemeinsamer Import-Einstiegspunkt.
- CAMT.052/053/054-Basisparser für XML-Kontoauszüge.
- MT940-Basisparser für `:61:`-Buchungen und strukturierte `:86:`-SEPA-Felder.
- Kontoabgleich-Oberfläche akzeptiert CSV, XML/CAMT, STA/MT940 und TXT.
- Bestehende Matching-, Teilzahlungs-, Sammelzahlungs- und Dublettenlogik bleibt erhalten.

## Qualität
- v0.6.2 Baseline vor Änderung: 24/24 Tests bestanden.
- v0.6.3-dev nach Änderung: 29/29 Tests bestanden.
- Python-Compile-Check erfolgreich.

## Noch offen vor produktiver Freigabe
- Validierung gegen echte CAMT-/MT940-Exporte der tatsächlich verwendeten Bank.
- Bankspezifische Varianten und Sonderfälle ergänzen.
- Import-Metadaten/Format optional dauerhaft in der DB speichern.
- Monatsaggregation und automatische Monatsablage.
- Danach v0.7 Finanz-Dashboard.
