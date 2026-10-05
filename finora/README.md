# Finora Dokument-Assistent v0.6.2

Lokaler Dokument-Assistent für Windows mit OCR, lernender Zuordnung, Stapelupload und CSV-Kontoabgleich.

## Bestehende Funktionen aus v0.5.1

- Mehrere PDF/JPG/PNG-Dateien gleichzeitig auswählen.
- Finora führt OCR für die Auswahl aus.
- Die Dokumente werden anschließend nacheinander in der bekannten Prüfmaske angezeigt.
- Nach `Bestätigen & speichern` öffnet sich automatisch das nächste Dokument im Stapel.
- Fortschrittsanzeige `Dokument X von Y`.
- Nach dem letzten Dokument erscheint eine Abschlussmeldung.
- Einzelupload funktioniert weiterhin unverändert.
- Alle Daten und Dateien bleiben lokal unter `C:\Finora`.

## Installation / Update

1. ZIP in einen neuen Programmordner entpacken, z. B. `C:\Finora-App-v0.6.2`.
2. `install_windows.bat` ausführen.
3. `start_windows.bat` ausführen.
4. Browser: `http://127.0.0.1:8020`.

Die vorhandenen Daten unter `C:\Finora` werden weiterverwendet.

## Stapelupload

Auf der Startseite im Dateidialog mehrere Dateien mit `Strg` oder `Shift` markieren. Danach `OCR für Auswahl starten` drücken. Finora zeigt die Dokumente einzeln zur Prüfung an.

## Unterstützte Dateien

- PDF
- JPG / JPEG
- PNG

## Hinweise

Für Bild-OCR muss Tesseract OCR auf Windows installiert und erreichbar sein. Text-PDFs werden direkt ausgelesen.

## Version 0.6.2 – Erweiterter Kontoabgleich

Neu:
- CSV-Import für das Berliner-Volksbank-Format.
- Dublettenprüfung per Zeilen-Prüfsumme.
- Anzeige von Bankbuchungen mit Buchungstag, Partner, Verwendungszweck, Betrag und Saldo.
- Automatische Vorschläge gegen bestätigte offene Ein- und Ausgangsrechnungen.
- Matching nach Betrag, Rechnungsnummer, Geschäftspartner und Zahlungsrichtung.
- Bestätigung setzt Rechnung auf `Bezahlt` oder `Teilbezahlt` und speichert das Zahlungsdatum.
- Grundlage für die Istversteuerungs-Monatslogik.

Neu in 0.6.2: manuelle Rechnungssuche, echte Teilzuordnung von Bankbuchungen, Sammelzahlungen auf mehrere Rechnungen und das Lösen/Korrigieren bestehender Zuordnungen. Noch nicht enthalten: CAMT/MT940 und automatische Monatsablage.

## Entwicklung v0.6.3-dev – gemeinsamer Bankimport

Begonnener nächster Entwicklungsschritt nach v0.6.2:

- Bankdatei-Parsing wurde aus der Matching-Logik herausgelöst (`app/bank_import.py`).
- Gemeinsame interne Transaktionsstruktur für CSV, CAMT und MT940.
- Bestehender Berliner-Volksbank-CSV-Import bleibt kompatibel.
- Erster Parser für CAMT.052/053/054-XML.
- Erster Parser für MT940 (`:61:`/`:86:`), inklusive Vorzeichen und strukturierten SEPA-Feldern.
- Oberfläche akzeptiert nun CSV, XML/CAMT, STA/MT940 und TXT.
- Matching, Teilzahlungen, Sammelzahlungen und Dublettenlogik bleiben unverändert angebunden.

**Status:** Entwicklungsstand. CAMT/MT940 sind mit synthetischen Fixtures getestet, aber noch nicht gegen echte Exporte der verwendeten Bank validiert. Vor einem produktiven Einsatz müssen reale Beispieldateien geprüft und bankspezifische Varianten ergänzt werden.
