# Backend

FastAPI-Integrationsschicht zwischen Schlemeier DMS und Finora.

## Endpunkte

- `GET /` – DMS-Oberfläche
- `GET /api/health` – Status
- `GET /api/documents` – offene und abgelegte Dokumente
- `GET /api/documents/{id}` – Dokumentmetadaten
- `GET /api/documents/{id}/file` – sichere Dokumentvorschau
- `POST /api/documents/{id}/decision` – offenen Beleg bestätigen und ablegen
- `GET /kontoabgleich` – Weiterleitung zum Finora-Kontoabgleich

## Grundsatz

Die DMS-Schicht dupliziert weder OCR noch Klassifikations- oder Matchinglogik. Sie verwendet direkt Finoras bestehende Funktionen und Datenbank. Benutzerkorrekturen werden als Lernbeispiele zurückgegeben.
