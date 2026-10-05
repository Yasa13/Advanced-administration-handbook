# Finora v0.6.3-dev

Entwicklungsstand auf Basis von v0.6.2.

## Neu
- Bankimport in separates Modul app/bank_import.py ausgelagert.
- Einheitliche interne Transaktionsstruktur für CSV, CAMT und MT940.
- Format-Erkennung und gemeinsamer Import-Einstiegspunkt.
- CAMT.052/053/054-Basisparser.
- MT940-Basisparser.
- Kontoabgleich-Oberfläche akzeptiert CSV, XML/CAMT, STA/MT940 und TXT.

## Qualität
- v0.6.2 Baseline: 24/24 Tests bestanden.
- v0.6.3-dev: 29/29 Tests bestanden.
- Python-Compile-Check erfolgreich.

## Noch offen
- Validierung gegen echte CAMT-/MT940-Exporte.
- Bankspezifische Varianten und Sonderfälle.
- Monatsaggregation und automatische Monatsablage.
- Danach v0.7 Finanz-Dashboard.
