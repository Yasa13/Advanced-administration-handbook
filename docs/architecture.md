# Architektur – Schlemeier DMS / Finora

## Zielbild

```text
Scanner / Upload / E-Mail / SharePoint / OneDrive
                    |
                    v
                 Finora
       OCR / Erkennung / Matching
                    |
                    v
              shared contracts
                    |
                    v
              Schlemeier DMS
      Prüfen / Suchen / Zuordnen
                    |
         +----------+----------+
         |                     |
         v                     v
       DMS-Ablage          Buchhaltung
                               |
                               v
                         Finanz-Dashboard
```

## Trennung der Verantwortlichkeiten

### Finora
- OCR
- Merkmalsextraktion
- Dokumentklassifikation
- Lernfunktion
- Bankimport CSV/CAMT/MT940
- Rechnungs-/Zahlungsmatching

### Schlemeier DMS
- zentrale Oberfläche
- Dokumentvorschau
- Miniaturansichten
- Benutzerkorrektur
- Zielauswahl
- Dublettenhinweise
- Such- und Filterfunktionen
- Status und Arbeitswarteschlange

### Shared
- Dokumentvertrag
- Firmen- und Privatzuordnung
- Banktransaktionsvertrag

## Datenprinzip

Schlemeier DMS darf Klassifikationen korrigieren.
Die bestätigte Korrektur wird anschließend an Finora zurückgegeben, damit die Lernfunktion verbessert wird.

## Sicherheitsprinzip

Keine Zugangsdaten, echten Belege, personenbezogenen Originaldokumente oder Bankdateien gehören in Git.
