# Finora Dokument-Assistent v0.6.3-dev

Lokaler Dokument-Assistent für Windows mit OCR, lernender Zuordnung, Stapelupload und erweitertem Kontoabgleich.

## Bestehende Funktionen aus v0.5.1
- Mehrere PDF/JPG/PNG-Dateien gleichzeitig auswählen.
- OCR für die Auswahl.
- Prüfmaske mit Fortschritt Dokument X von Y.
- Lernende Zuordnung.
- Lokale Datenhaltung unter C:\\Finora.

## v0.6.2 – Kontoabgleich
- CSV-Import für das Berliner-Volksbank-Format.
- Dublettenprüfung per Zeilen-Prüfsumme.
- Matching nach Betrag, Rechnungsnummer, Geschäftspartner und Zahlungsrichtung.
- Teilzahlungen, Sammelzahlungen und manuelle Zuordnung.

## v0.6.3-dev
- Bankdatei-Parsing aus der Matching-Logik ausgelagert.
- Gemeinsame interne Transaktionsstruktur für CSV, CAMT und MT940.
- Erster Parser für CAMT.052/053/054.
- Erster MT940-Parser.
- Oberfläche akzeptiert CSV, XML/CAMT, STA/MT940 und TXT.
- Bestehende Matching-, Teilzahlungs-, Sammelzahlungs- und Dublettenlogik bleibt angebunden.

## Qualität
- v0.6.2 Baseline: 24/24 Tests bestanden.
- v0.6.3-dev: 29/29 Tests bestanden.
- Python-Compile-Check erfolgreich.

## Status
Entwicklungsstand. CAMT/MT940 sind mit synthetischen Fixtures getestet, aber noch nicht gegen echte Exporte der verwendeten Bank validiert.
