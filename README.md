# SignalDesk

SignalDesk zeigt die volumenstärksten aktiven Polymarket-Märkte einer Kategorie
und ordnet ihre Wahrscheinlichkeiten mit OpenAI strukturiert ein.

> Die KI-Ausgaben dienen ausschließlich Informationszwecken und sind keine
> Finanzberatung.

## Funktionen

- Aktuelle Kategorien und Märkte aus der Polymarket Gamma API
- Top 5, 10, 15 oder 25 Märkte nach Handelsvolumen
- Volumen, Liquidität und implizite Wahrscheinlichkeiten
- Strukturierte KI-Analyse über die OpenAI Responses API
- Responsives, barrierearmes Frontend ohne Build-Schritt
- API-Fehlerbehandlung, Healthcheck und fünfminütiger Daten-Cache
- Tests, Linting, GitHub Actions und Docker-Deployment

## Lokal starten

Voraussetzungen: Python 3.11 oder neuer und ein OpenAI API-Schlüssel.

```bash
python -m venv .venv
```

Aktiviere die virtuelle Umgebung:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Installiere die Pakete und lege deine lokale Konfiguration an:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Unter Windows kannst du `.env.example` manuell als `.env` kopieren. Trage dort
deinen Schlüssel als `OPENAI_API_KEY` ein. Die `.env`-Datei wird nicht
versioniert.

```bash
uvicorn app:app --reload
```

Danach ist die Anwendung unter <http://localhost:8000> erreichbar. Die
interaktive API-Dokumentation liegt unter <http://localhost:8000/docs>.

## Konfiguration

| Variable | Standard | Beschreibung |
| --- | --- | --- |
| `OPENAI_API_KEY` | – | Erforderlich für KI-Analysen |
| `OPENAI_MODEL` | `gpt-5.6-sol` | Verwendetes OpenAI-Modell |
| `HOST` | `0.0.0.0` | Server-Adresse |
| `PORT` | `8000` | Server-Port |
| `ENVIRONMENT` | `development` | Laufzeitumgebung |

## API

| Methode | Route | Zweck |
| --- | --- | --- |
| `GET` | `/api/health` | Status und OpenAI-Konfiguration |
| `GET` | `/api/categories` | Verfügbare Kategorien |
| `GET` | `/api/markets/{id}?limit=10` | Top-Märkte einer Kategorie |
| `POST` | `/api/analyze?category_id={id}&limit=10` | KI-Analyse |

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

## Deployment

### Docker

```bash
docker build -t signaldesk .
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-... signaldesk
```

### Render

Das Repository enthält eine `render.yaml`. Verbinde das Repository in Render
als Blueprint und hinterlege `OPENAI_API_KEY` als Secret. Render baut dann das
Docker-Image und überwacht `/api/health`.

## Architektur

```text
.
├── app.py                  # FastAPI-Routen und statische Auslieferung
├── models.py               # Validierte API-Datenmodelle
├── polymarket_client.py    # Polymarket-Zugriff, Parsing und Cache
├── openai_analyzer.py      # Responses API und strukturierte Ausgabe
├── static/                 # HTML, CSS und JavaScript
├── tests/                  # Automatisierte Tests
├── Dockerfile              # Produktions-Container
└── .github/workflows/      # CI für Tests und Linting
```

## Sicherheit

- API-Schlüssel bleiben ausschließlich im Backend.
- `.env` ist in `.gitignore` ausgeschlossen.
- Externe Texte werden im Browser als Text gerendert, nicht als ungeprüftes HTML.
- Der Container läuft als Benutzer ohne Root-Rechte.

<!-- hypertribe:sponsors:start -->
## Sponsors

[![predict_withFun Sponsors](https://api.tribe.run/tokens/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU/sponsors.svg)](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU)

Become a sponsor on [Tribe.run](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU).
<!-- hypertribe:sponsors:end -->
