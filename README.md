# predict_withFun

predict_withFun displays the highest-volume active Polymarket markets in a
category and uses OpenAI to provide structured context for their probabilities.

> AI-generated results are for informational purposes only and are not
> financial advice.

## Features

- Current categories and markets from the Polymarket Gamma API
- Top 5, 10, 15, or 25 markets by trading volume
- Volume, liquidity, and implied probabilities
- Structured AI analysis through the OpenAI Responses API
- Live web research with source links for current evidence
- Selectable OpenAI web research or Grok real-time X research
- One-click analysis and one-month price history for individual markets
- Instant title search plus volume, liquidity, and probability sorting
- Device-local watchlist stored in the browser
- Side-by-side comparison for up to three markets
- CSV and JSON export of the current filtered view
- Demo mode that works without an OpenAI API key
- Per-client analysis limits to control API spend
- Responsive, accessible frontend with no build step
- API error handling, health check, and a five-minute data cache
- Tests, linting, GitHub Actions, and Docker deployment

## Run locally

Requirements: Python 3.11 or newer and an OpenAI API key.

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install the packages and create your local configuration:

```bash
pip install -r requirements.txt
cp .env.example .env
```

On Windows, you can manually copy `.env.example` to `.env`. Add your key as
`OPENAI_API_KEY`. The `.env` file is excluded from version control.

```bash
uvicorn app:app --reload
```

Open <http://localhost:8000>. Interactive API documentation is available at
<http://localhost:8000/docs>.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | Required for AI analysis |
| `OPENAI_MODEL` | `gpt-5.6-sol` | OpenAI model used for analysis |
| `OPENAI_REASONING_EFFORT` | `low` | Reasoning level for analysis |
| `XAI_API_KEY` | — | Required for Grok and real-time X research |
| `XAI_MODEL` | `grok-4.5` | Grok model used for X research |
| `DEMO_MODE` | `true` | Return a market-price demo when no API key is set |
| `ANALYSIS_REQUESTS_PER_HOUR` | `5` | Analysis limit per client IP |
| `HOST` | `0.0.0.0` | Server address |
| `PORT` | `8000` | Server port |
| `ENVIRONMENT` | `development` | Runtime environment |

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service and OpenAI configuration status |
| `GET` | `/api/categories` | Available categories |
| `GET` | `/api/markets/{id}?limit=10` | Top markets in a category |
| `POST` | `/api/analyze?category_id={id}&provider=grok` | AI analysis |
| `POST` | `/api/analyze/{category_id}/{market_slug}?provider=grok` | Single-market analysis |
| `GET` | `/api/history/{category_id}/{market_slug}` | Market price history |

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

## Deployment

### Docker

```bash
docker build -t predict-with-fun .
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-... predict-with-fun
```

### Render

The repository includes a `render.yaml` file. Connect the repository in Render
as a Blueprint and store `OPENAI_API_KEY` as a secret. Render will build the
Docker image and monitor `/api/health`.

## Architecture

```text
.
├── app.py                  # FastAPI routes and static file delivery
├── models.py               # Validated API data models
├── polymarket_client.py    # Polymarket client, parsing, and cache
├── openai_analyzer.py      # Responses API and structured output
├── static/                 # HTML, CSS, and JavaScript
├── tests/                  # Automated tests
├── Dockerfile              # Production container
└── .github/workflows/      # CI for tests and linting
```

## Security

- API keys remain on the backend.
- `.env` is excluded through `.gitignore`.
- External text is rendered as text rather than untrusted HTML.
- The container runs as a non-root user.

<!-- hypertribe:sponsors:start -->
## Sponsors

[![predict_withFun Sponsors](https://api.tribe.run/tokens/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU/sponsors.svg)](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU)

Become a sponsor on [Tribe.run](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU).
<!-- hypertribe:sponsors:end -->
