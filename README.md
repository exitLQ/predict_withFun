# Polymarket Analysis Tool

Ein Web-Tool zur Analyse von Polymarket-Märkten mit KI-Unterstützung durch OpenAI.

## Features

- Abruf aller aktuellen Märkte von Polymarket
- Anzeige der Top 10 Märkte pro Kategorie (sortiert nach Volumen)
- KI-gestützte Analyse der Marktwahrscheinlichkeiten mit OpenAI GPT-4
- Moderne Web-UI zur interaktiven Nutzung

## Installation

1. Python 3.8+ installieren

2. Dependencies installieren:
```bash
pip install -r requirements.txt
```

3. OpenAI API Key konfigurieren:
```bash
export OPENAI_API_KEY=your_api_key_here
```

Oder erstelle eine `.env` Datei:
```
OPENAI_API_KEY=your_api_key_here
```

## Verwendung

1. Server starten:
```bash
python app.py
```

Oder mit uvicorn direkt:
```bash
uvicorn app:app --reload
```

2. Browser öffnen:
```
http://localhost:8000
```

3. Im Browser:
   - Kategorie auswählen
   - "Märkte laden" klicken, um die Top 10 Märkte zu sehen
   - "Analyse starten" klicken, um eine KI-Analyse durchzuführen

## API Endpunkte

- `GET /api/categories` - Liste aller Kategorien
- `GET /api/markets/{category_id}` - Top 10 Märkte einer Kategorie
- `POST /api/analyze?category_id={id}` - KI-Analyse der Märkte einer Kategorie

## Projektstruktur

```
prediction_tool/
├── app.py                 # FastAPI Backend
├── polymarket_client.py   # Polymarket API Client
├── openai_analyzer.py     # OpenAI Analyse-Logik
├── models.py              # Datenmodelle
├── static/                # Frontend
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt       # Python Dependencies
└── README.md
```

## Technologie-Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript
- **APIs**: 
  - Polymarket Gamma API
  - OpenAI API (GPT-4)
