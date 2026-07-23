# Polymarket Analysis Tool

A web tool for analyzing Polymarket markets with AI support powered by OpenAI.

## Features

- Fetch all current markets from Polymarket
- Display the top 10 markets per category (sorted by volume)
- AI-powered analysis of market probabilities with OpenAI GPT-4
- Modern web UI for interactive use

## Installation

1. Install Python 3.8+

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your OpenAI API key:
```bash
export OPENAI_API_KEY=your_api_key_here
```

Or create a `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

## Usage

1. Start the server:
```bash
python app.py
```

Or directly with uvicorn:
```bash
uvicorn app:app --reload
```

2. Open your browser:
```
http://localhost:8000
```

3. In the browser:
   - Select a category
   - Click "Load Markets" to see the top 10 markets
   - Click "Start Analysis" to run an AI analysis

## API Endpoints

- `GET /api/categories` - List of all categories
- `GET /api/markets/{category_id}` - Top 10 markets of a category
- `POST /api/analyze?category_id={id}` - AI analysis of a category's markets

## Project Structure

```
prediction_tool/
├── app.py                 # FastAPI backend
├── polymarket_client.py   # Polymarket API client
├── openai_analyzer.py     # OpenAI analysis logic
├── models.py              # Data models
├── static/                # Frontend
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt       # Python dependencies
└── README.md
```

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript
- **APIs**: 
  - Polymarket Gamma API
  - OpenAI API (GPT-4)

<!-- hypertribe:sponsors:start -->
## Sponsors

[![predict_withFun Sponsors](https://api.tribe.run/tokens/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU/sponsors.svg)](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU)

Become a sponsor on [Tribe.run](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU).
<!-- hypertribe:sponsors:end -->
