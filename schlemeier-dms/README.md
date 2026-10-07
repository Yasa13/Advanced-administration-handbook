# Schlemeier DMS

Zentrale Oberfläche für den PSS-Dokumentenworkflow mit direkter Finora-Anbindung.

## Aktueller Integrationsstand

Implementiert:

- Dokumentliste aus Finora-Inbox und Finora-Archiv
- PDF-/Bildvorschau und Miniaturansicht
- Suche sowie Status- und Bereichsfilter
- Finora-Klassifikationsvorschlag für offene Belege
- Auswahl **„Wo gehört der Beleg hin?“**
- Ziele PSS, Berliner Paletten, Paletten-Service Spandau und Privat
- Privatpersonen Yasmin, Frank, Marina und Karl
- Bestätigte Ablage in Finoras bestehende Ordnerlogik
- bestätigte Korrekturen werden an Finoras Lernfunktion zurückgegeben
- Link zum bestehenden Finora-Kontoabgleich

## Start unter Windows

1. Finora wie bisher installieren.
2. Finora über `finora/start_windows.bat` starten. Der Kontoabgleich läuft unter Port 8020.
3. `schlemeier-dms/start_dms.bat` starten.
4. Browser: `http://127.0.0.1:8030`.

Beide Module verwenden denselben lokalen Finora-Datenbestand unter `C:\Finora`.

## Architektur

- **Schlemeier DMS** = Oberfläche, Prüfung, Vorschau, Zielauswahl und Status
- **Finora** = OCR, Klassifikation, Lernfunktion, Dateiablage und Kontoabgleich
- **shared/** = gemeinsame Dokument-, Klassifikations- und Bankmodelle

## Statusmodell

- `Pruefen` = Datei liegt noch in Finoras Eingang und wartet auf Bestätigung.
- `Abgelegt` = Datei wurde bestätigt, protokolliert und in Finoras Ablage gespeichert.

Die bereits vorgesehenen Statuswerte `Neu`, `Zugeordnet` und `Duplikat` werden in späteren Integrationsstufen weiter ausgebaut.

## Aktuelle Grenzen

- Bereits abgelegte Dokumente werden in dieser Version nur angezeigt; ein nachträgliches Verschieben erfolgt noch nicht über das DMS.
- Automatische Dublettenprüfung ist noch nicht Teil dieser ersten UI-Integration.
- Das Finanz-Dashboard ist für v0.7 vorgesehen.
- Der ursprüngliche Seitenquellstand der veröffentlichten Schlemeier-DMS-Seite war über die aktuelle Projektverbindung nicht abrufbar. Die integrierte Oberfläche wurde deshalb auf Basis des bestätigten Funktionsumfangs rekonstruiert.

## Tests

Der Integrationsstand wurde zusammen mit Finora getestet:

- 29 bestehende Finora-Tests
- 3 neue DMS-Integrationstests
- **32/32 Tests bestanden**
