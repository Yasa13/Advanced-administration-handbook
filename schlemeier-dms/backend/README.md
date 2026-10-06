# Backend

Backend-Grenze zwischen Schlemeier DMS und Finora.

## Verantwortlichkeiten

- Dokumentliste bereitstellen
- Dokumentdetails und Thumbnail-Referenzen liefern
- Klassifikationsvorschläge von Finora übernehmen
- Benutzerkorrekturen an Finora zurückgeben
- Ablageziel verwalten
- Dublettenstatus führen
- Banktransaktionen und Matching-Status bereitstellen

## Grundsatz

Die UI soll keine eigene OCR-, Matching- oder Klassifikationslogik duplizieren.
Diese Logik bleibt in Finora und wird über gemeinsame Verträge aus shared/ angesprochen.
