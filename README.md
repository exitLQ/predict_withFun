# predict_withFun

predict_withFun is a web application for exploring active Polymarket prediction
markets and comparing market prices with source-backed AI research.

The application combines current Polymarket data with one of three research
providers:

- OpenAI with web search
- Grok with real-time X search
- Claude with web search

It can also run all configured providers in parallel and display their
estimates side by side.

> AI-generated results are for informational purposes only. They are not
> financial advice and do not predict future outcomes with certainty.

## Table of contents

- [Features](#features)
- [How it works](#how-it-works)
- [Research providers](#research-providers)
- [User guide](#user-guide)
- [Local installation](#local-installation)
- [Configuration](#configuration)
- [Caching, fallback, and rate limits](#caching-fallback-and-rate-limits)
- [Persistent analysis history](#persistent-analysis-history)
- [Accuracy tracking](#accuracy-tracking)
- [Provider synthesis](#provider-synthesis)
- [Cost estimates](#cost-estimates)
- [API reference](#api-reference)
- [Data models](#data-models)
- [Testing and continuous integration](#testing-and-continuous-integration)
- [Deployment](#deployment)
- [Architecture](#architecture)
- [Security and privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)

## Features

### Market discovery

- Loads current categories from the Polymarket Gamma API
- Displays the top 5, 10, 15, or 25 active markets by volume
- Shows implied probability, volume, liquidity, outcome, and Polymarket link
- Provides instant title search
- Sorts by volume, liquidity, or probability
- Loads one-month price history for individual markets

### Research and analysis

- Produces structured probability assessments in English
- Separates the observed market probability from the AI fair-probability estimate
- Labels each market as `undervalued`, `fair`, or `overvalued`
- Includes reasoning, uncertainty, risks, and source links
- Supports category-wide and individual-market analysis
- Supports OpenAI web research, Grok X research, and Claude web research
- Compares all configured providers side by side
- Falls back to another configured provider after a provider failure

### Cost and performance controls

- Caches identical analyses for 30 minutes by default
- Shows whether a result came from the cache
- Reports input tokens, output tokens, and detected search calls
- Calculates an estimated USD cost for each new analysis
- Applies a configurable per-client analysis limit
- Caches Polymarket data for five minutes
- Stores completed live analyses in PostgreSQL or local SQLite
- Scores resolved forecasts with Brier score and compares AI with the market
- Builds an accuracy-weighted consensus from provider comparison results

### Browser tools

- Stores a device-local watchlist in `localStorage`
- Compares up to three selected markets
- Exports the currently filtered market list as CSV or JSON
- Uses responsive HTML, CSS, and JavaScript without a frontend build step

### Engineering

- FastAPI backend with validated Pydantic response models
- Interactive OpenAPI documentation
- Automated tests and Ruff linting
- GitHub Actions continuous integration
- Docker and Render deployment configuration
- Non-root production container

## How it works

The normal request flow is:

1. The browser requests categories and markets from the FastAPI backend.
2. The backend retrieves and normalizes public Polymarket data.
3. The user selects a provider and starts an analysis.
4. The backend checks the per-client request limit.
5. It builds a cache key from the provider, category, market slugs, and current
   first-outcome probabilities.
6. A valid cached result is returned immediately when available.
7. Otherwise, the selected AI provider researches current evidence and returns
   a structured analysis.
8. The backend normalizes provider output, extracts sources and usage data, and
   estimates the request cost.
9. If the provider fails and fallback is enabled, another configured provider
   is tried.
10. The result is cached and displayed in the browser.

Provider comparison uses the same pipeline but starts each configured provider
in parallel. A failure from one provider does not discard successful results
from the others.

## Research providers

| Provider | API key | Default model | Research tool | Provider value |
| --- | --- | --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `gpt-5.6-sol` | Web search | `openai` |
| Grok / xAI | `XAI_API_KEY` | `grok-4.5` | X search | `grok` |
| Claude / Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-5` | Web search | `claude` |

Only backend code can access the API keys. The browser sends a provider name,
never a secret.

### OpenAI

OpenAI analysis uses the Responses API, structured Pydantic output, web search,
and a configurable reasoning level. The backend requests web-search source
details and extracts usable source URLs from the response.

### Grok and X research

Grok uses the OpenAI-compatible xAI endpoint at `https://api.x.ai/v1`. Its
`x_search` tool researches current X posts, accounts, and threads. A prompt
cache key is included to allow provider-side reuse where supported.

### Claude and Anthropic

Claude uses the native Anthropic Python SDK, structured output, and the
server-side `web_search_20250305` tool. A research call can perform up to three
web searches.

Claude Code is Anthropic's separate development agent. predict_withFun does not
run Claude Code inside the application; it connects directly to a Claude model
through the Anthropic API.

### Compare all providers

Select **Compare all providers** to analyze the current category with every
configured provider. Results appear in separate columns on wide screens and
stack vertically on smaller screens.

Comparison behavior:

- Only providers with API keys are used in live mode.
- All three providers are shown in demo mode when no keys are configured.
- Providers run concurrently to reduce total waiting time.
- Fallback is disabled inside a comparison so one provider cannot impersonate
  another provider's result.
- Provider-specific failures are returned in the `errors` object while
  successful analyses remain available.
- A comparison can create up to three billable provider requests on a cache miss.

## User guide

### Explore markets

1. Open the application.
2. Select a Polymarket category.
3. Select how many markets to load.
4. Select OpenAI, Grok, Claude, or **Compare all providers**.
5. Click **Show markets**.

Use the search and sort controls to narrow the result list.

### Analyze a category

After loading markets, click **Analyze with AI**. Category analysis is limited
to the first ten markets even if 15 or 25 markets are displayed. This keeps
prompts and costs bounded.

The result contains:

- the provider that actually produced the result;
- a category summary;
- overall insights;
- market and fair probabilities;
- valuation assessment;
- reasoning and risks;
- source links;
- cache and fallback status;
- token usage, search usage, and estimated cost.

### Analyze one market

Click **Analyze** on a market card. Individual analysis works with OpenAI,
Grok, or Claude. If **Compare all providers** is selected, the interface asks
you to use category comparison instead.

### View price history

Click **History** on a market card to request up to 60 points of one-month
history for the first outcome. Markets without a usable token ID return an
empty history.

### Watchlist and comparison

- **Watch** saves a market slug in the current browser's `localStorage`.
- **Compare** adds a market to the browser-side market comparison.
- Up to three markets can be compared at once.
- Watchlists are device-local and are not synchronized between browsers.

### Export

CSV and JSON export use the currently visible, filtered, and sorted markets.
Exports include title, probability, volume, liquidity, category, and URL.

## Local installation

### Requirements

- Python 3.11 or newer
- `pip`
- At least one provider API key for live research

An API key is optional when demo mode is enabled.

### 1. Clone the repository

```bash
git clone https://github.com/exitLQ/predict_withFun.git
cd predict_withFun
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create the environment file

macOS or Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and add the API keys you want to use. The file is excluded from
Git and must never be committed.

### 5. Start the application

```bash
uvicorn app:app --reload
```

Open:

- Application: <http://localhost:8000>
- Swagger API documentation: <http://localhost:8000/docs>
- ReDoc documentation: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/api/health>

## Configuration

### Provider configuration

| Variable | Default | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | OpenAI secret API key |
| `OPENAI_MODEL` | `gpt-5.6-sol` | OpenAI model used for analysis |
| `OPENAI_REASONING_EFFORT` | `low` | OpenAI reasoning effort |
| `XAI_API_KEY` | — | xAI secret API key |
| `XAI_MODEL` | `grok-4.5` | Grok model used for X research |
| `ANTHROPIC_API_KEY` | — | Anthropic secret API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Claude model used for web research |

Changing a model may require updating its cost variables. The replacement
model must support the structured-output and research tools used by the
application.

### Application behavior

| Variable | Default | Description |
| --- | --- | --- |
| `DEMO_MODE` | `true` | Return non-researched demo output when the selected provider has no key |
| `PROVIDER_FALLBACK` | `true` | Try another configured provider after an unavailable-provider error |
| `ANALYSIS_CACHE_TTL` | `1800` | Analysis-cache lifetime in seconds |
| `ANALYSIS_REQUESTS_PER_HOUR` | `5` | Maximum analysis requests per client IP and process |
| `ENVIRONMENT` | `development` | Enables reload only when running `python app.py` in development |
| `HOST` | `0.0.0.0` | Bind address when running `python app.py` |
| `PORT` | `8000` | HTTP port |
| `DATABASE_URL` | `sqlite:///./predict_withfun.db` | PostgreSQL or SQLite connection URL |

Boolean values are enabled only when their value is `true`, ignoring letter
case.

### Cost configuration

All cost rates are expressed in USD.

| Variable | Default | Unit |
| --- | ---: | --- |
| `OPENAI_INPUT_USD_PER_MTOK` | `5` | One million input tokens |
| `OPENAI_OUTPUT_USD_PER_MTOK` | `30` | One million output tokens |
| `OPENAI_SEARCH_USD_PER_1K` | `10` | One thousand searches |
| `XAI_INPUT_USD_PER_MTOK` | `2` | One million input tokens |
| `XAI_OUTPUT_USD_PER_MTOK` | `6` | One million output tokens |
| `XAI_SEARCH_USD_PER_1K` | `5` | One thousand searches |
| `ANTHROPIC_INPUT_USD_PER_MTOK` | `2` | One million input tokens |
| `ANTHROPIC_OUTPUT_USD_PER_MTOK` | `10` | One million output tokens |
| `ANTHROPIC_SEARCH_USD_PER_1K` | `10` | One thousand searches |

The defaults reflect the documented standard prices for the default models as
of July 2026. Check provider pricing before changing models or relying on these
figures for budgeting.

## Caching, fallback, and rate limits

### Analysis cache

The analysis cache is an in-memory dictionary inside the application process.
Its key includes:

- selected provider;
- category name;
- market slugs;
- current first-outcome probabilities.

The default time to live is 1,800 seconds. A cache hit returns `cached: true`,
preserves the original token counts for transparency, and reports zero new
estimated API cost.

Important cache properties:

- The cache is cleared whenever the process restarts.
- Separate application instances do not share entries.
- Changing the TTL does not persist existing entries.
- The cache is not a historical-analysis database.

### Automatic provider fallback

Fallback applies to normal category and single-market analyses. The order is:

1. requested provider;
2. OpenAI, Grok, and Claude in their fixed order, excluding the requested provider.

Providers without a configured key are skipped when at least one candidate is
configured. The response exposes:

- `requested_provider`: the provider selected by the user;
- `research_provider`: the provider that produced the result;
- `fallback_used`: whether those values differ.

Set `PROVIDER_FALLBACK=false` to disable this behavior.

Fallback handles provider rate limits, connection errors, and API status
errors that are converted to `AIUnavailableError`. It does not hide invalid
application requests or Polymarket errors.

### Request limiting

Analysis endpoints use an in-memory sliding one-hour window keyed by client IP.
The default limit is five requests per hour.

- Category analysis counts as one request.
- Single-market analysis counts as one request.
- Provider comparison counts as one application request even though it may
  call multiple providers.
- Market browsing and price-history requests are not included.

The limiter is process-local. For a multi-instance public deployment, replace
it with a shared store such as Redis if strict global enforcement is required.

## Persistent analysis history

Every new, non-demo, non-cached analysis is stored after it completes.
Comparison requests store each successful provider result separately. Cache
hits are not duplicated.

Production uses PostgreSQL through `DATABASE_URL`; local development defaults
to a SQLite file so the application remains easy to run. The database stores:

- creation time and unique record ID;
- category and provider metadata;
- complete validated analysis JSON;
- market count and estimated request cost;
- optional resolution and accuracy fields used by later scoring.

The schema and index are created automatically on first use. History can be
listed with `GET /api/analyses` and an original result can be retrieved with
`GET /api/analyses/{record_id}`.

## Accuracy tracking

Every stored market forecast creates a separate scoring record containing the
provider's fair probability and the market probability observed at analysis
time. Click **Check resolutions** or call `POST /api/accuracy/sync` to inspect
unresolved markets through Polymarket's market-by-slug endpoint.

A closed market is scored only when its first-outcome settlement price is
unambiguous: at least `0.999` for outcome `1`, or at most `0.001` for outcome
`0`. Ambiguous and unresolved markets remain pending.

The Brier score for a binary forecast is:

```text
(predicted probability - actual outcome)²
```

Lower scores are better. A perfect forecast scores `0`; a completely wrong
certain forecast scores `1`. The accuracy dashboard reports per provider:

- number of resolved forecasts;
- mean AI Brier score;
- mean Brier score of the market probability captured at analysis time;
- whether the provider outperformed or underperformed that market baseline;
- mean absolute probability error.

Historical forecasts are never rewritten when market prices change. Only the
eventual outcome and derived score are added.

## Provider synthesis

Every successful provider comparison includes a deterministic synthesis. For
each market, it calculates:

- arithmetic mean and median provider probability;
- minimum, maximum, and full provider spread;
- accuracy-weighted consensus probability;
- disagreement level;
- consensus valuation relative to the market;
- participating providers and combined unique risks.

Provider weights are based on inverse historical mean Brier score. Lower Brier
scores receive more weight. A provider without resolved forecasts receives a
neutral provisional Brier score of `0.25`. Scores are floored at `0.05` before
inversion so a small sample of perfect forecasts cannot create an unbounded
weight. The raw weights are normalized to sum to `1`.

| Spread between highest and lowest estimate | Disagreement |
| --- | --- |
| Up to 5 percentage points | `low` |
| More than 5 and up to 15 percentage points | `moderate` |
| More than 15 percentage points | `high` |

The weighted probability is compared with the current market probability. A
difference of at least five percentage points is classified as `undervalued`
or `overvalued`; smaller differences are classified as `fair`.

Synthesis is computed locally from validated results and does not make another
paid AI request.

## Cost estimates

The estimated cost is:

```text
(input tokens × input USD per MTok / 1,000,000)
+ (output tokens × output USD per MTok / 1,000,000)
+ (search calls × search USD per 1K / 1,000)
```

Usage data is taken from the provider response. Search calls are read from
provider usage fields when available and otherwise detected from tool-call
objects.

The displayed number is an estimate, not an invoice. Actual billing can differ
because of:

- cached-token pricing;
- long-context pricing;
- regional or priority-processing multipliers;
- reasoning-token accounting;
- provider-side discounts;
- searches or tools not reported in the expected response field;
- model-price changes after the documented defaults were set.

Always use the provider billing console as the authoritative cost source.

## API reference

All JSON API routes use the `/api` prefix.

### `GET /api/health`

Returns service status, configured providers, and whether the application is
currently in demo mode.

Example:

```bash
curl http://localhost:8000/api/health
```

```json
{
  "status": "ok",
  "openai_configured": true,
  "grok_configured": false,
  "claude_configured": true,
  "demo_mode": false
}
```

The endpoint confirms that keys exist; it does not make paid provider requests
or validate the keys.

### `GET /api/categories`

Returns available Polymarket categories.

```bash
curl http://localhost:8000/api/categories
```

### `GET /api/markets/{category_id}`

Returns active markets for a category, ordered by volume.

Query parameters:

| Parameter | Default | Validation |
| --- | --- | --- |
| `limit` | `10` | Integer from 1 to 25 |

```bash
curl "http://localhost:8000/api/markets/1?limit=10"
```

### `POST /api/analyze`

Analyzes the leading markets in a category.

Query parameters:

| Parameter | Required | Default | Validation |
| --- | --- | --- | --- |
| `category_id` | Yes | — | Non-empty string |
| `limit` | No | `10` | Integer from 1 to 10 |
| `provider` | No | `openai` | `openai`, `grok`, or `claude` |

```bash
curl -X POST \
  "http://localhost:8000/api/analyze?category_id=1&limit=5&provider=claude"
```

Abbreviated response:

```json
{
  "category": "Politics",
  "summary": "Current evidence suggests...",
  "markets": [
    {
      "market_slug": "example-market",
      "market_title": "Will the event happen?",
      "fair_probability": 0.57,
      "market_probability": 0.61,
      "assessment": "overvalued",
      "risks": ["Late-breaking information"],
      "reasoning": "The estimate reflects..."
    }
  ],
  "overall_insights": "Liquidity and timing remain important.",
  "sources": [
    {
      "title": "Primary source",
      "url": "https://example.com/source"
    }
  ],
  "demo": false,
  "research_provider": "claude",
  "requested_provider": "claude",
  "fallback_used": false,
  "cached": false,
  "usage": {
    "input_tokens": 2500,
    "output_tokens": 800,
    "search_calls": 2,
    "estimated_cost_usd": 0.033
  },
  "disclaimer": "AI-generated assessment for informational purposes only — not financial advice."
}
```

### `POST /api/compare`

Runs all configured providers concurrently for the same category and markets.

Query parameters:

| Parameter | Required | Default | Validation |
| --- | --- | --- | --- |
| `category_id` | Yes | — | Non-empty string |
| `limit` | No | `10` | Integer from 1 to 10 |

```bash
curl -X POST \
  "http://localhost:8000/api/compare?category_id=1&limit=5"
```

Response shape:

```json
{
  "results": [
    {
      "research_provider": "openai",
      "requested_provider": "openai",
      "fallback_used": false
    }
  ],
  "errors": {
    "grok": "The selected research provider is currently unavailable."
  }
}
```

Each object in `results` is a complete `AnalysisResult`. The abbreviated
example omits its other required fields for readability. The response also
contains `synthesis`, including normalized `provider_weights` and one
consensus record per analyzed market.

### `POST /api/analyze/{category_id}/{market_slug}`

Analyzes one market.

Query parameters:

| Parameter | Default | Validation |
| --- | --- | --- |
| `provider` | `openai` | `openai`, `grok`, or `claude` |

```bash
curl -X POST \
  "http://localhost:8000/api/analyze/1/example-market?provider=grok"
```

### `GET /api/history/{category_id}/{market_slug}`

Returns price-history points for the market's first outcome.

Query parameters:

| Parameter | Default | Allowed values |
| --- | --- | --- |
| `interval` | `1m` | `1h`, `6h`, `1d`, `1w`, `1m`, `max` |

```bash
curl \
  "http://localhost:8000/api/history/1/example-market?interval=1m"
```

Response:

```json
[
  {
    "timestamp": 1784764800,
    "price": 0.61
  }
]
```

### `GET /api/analyses`

Lists saved analysis metadata in reverse chronological order.

| Parameter | Default | Validation |
| --- | --- | --- |
| `limit` | `25` | Integer from 1 to 100 |

```bash
curl "http://localhost:8000/api/analyses?limit=25"
```

### `GET /api/analyses/{record_id}`

Returns the complete saved `AnalysisResult` for one history record.

```bash
curl "http://localhost:8000/api/analyses/RECORD_ID"
```

### `GET /api/accuracy`

Returns provider-level accuracy aggregates for resolved forecasts.

```bash
curl http://localhost:8000/api/accuracy
```

### `GET /api/accuracy/forecasts`

Returns individual pending and resolved forecast records. The optional `limit`
parameter defaults to `100` and accepts values from 1 to 1,000.

### `POST /api/accuracy/sync`

Checks unresolved market slugs against Polymarket and scores newly resolved
forecasts. The optional `limit` defaults to `100` and accepts values from 1 to
500.

```bash
curl -X POST "http://localhost:8000/api/accuracy/sync?limit=100"
```

### Status codes

| Status | Meaning |
| --- | --- |
| `200` | Successful request |
| `404` | Category or market was not found |
| `422` | Query parameter validation failed |
| `429` | Per-client analysis limit was reached |
| `502` | Polymarket request or data processing failed |
| `503` | No provider is available or provider research failed |

## Data models

### Market

A normalized market contains:

- `slug`
- `title`
- optional `description`
- `volume`
- optional `liquidity`
- `outcomes`
- optional `category`
- `active`
- optional Polymarket `url`
- optional first-outcome `token_id`

Outcome prices and probabilities are normalized to values from `0` through `1`.

### MarketAnalysis

Each generated market assessment contains:

- the original slug and title;
- observed market probability;
- optional AI fair probability;
- normalized assessment;
- up to five risks;
- provider reasoning.

### AnalysisResult

The top-level result includes analysis content, sources, provider metadata,
cache status, usage, estimated cost, and the financial disclaimer.

### ProviderComparison

Comparison responses contain a list of successful `AnalysisResult` objects and
an `errors` mapping keyed by provider name.

## Testing and continuous integration

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run linting:

```bash
ruff check .
```

Run tests:

```bash
python -m pytest -vv
```

The test suite covers:

- health and category endpoints;
- demo comparison for all providers;
- Polymarket parsing;
- OpenAI, Grok, and Claude provider selection in demo mode;
- analysis-cache behavior;
- automatic fallback;
- usage and cost calculation.
- persistent history round trips and skipped demo/cache records;
- resolution parsing, Brier scoring, and provider accuracy summaries.
- provider weighting, consensus probabilities, and disagreement classification.

GitHub Actions installs `requirements-dev.txt`, runs Ruff, and executes pytest
on every configured workflow trigger. A red workflow means at least one lint
or test step failed; expand the failing step in the Actions run for details.

## Deployment

### Docker

Build the image:

```bash
docker build -t predict-with-fun .
```

Run with OpenAI:

```bash
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  predict-with-fun
```

Run with multiple providers:

```bash
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e XAI_API_KEY=xai-... \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  predict-with-fun
```

PowerShell equivalent:

```powershell
docker run --rm -p 8000:8000 `
  -e OPENAI_API_KEY=sk-... `
  -e XAI_API_KEY=xai-... `
  -e ANTHROPIC_API_KEY=sk-ant-... `
  predict-with-fun
```

The container:

- uses Python 3.13 slim;
- installs pinned production dependencies;
- runs as a non-root `app` user;
- exposes port `8000`;
- includes an HTTP health check;
- starts Uvicorn in production mode.

### Render

The included `render.yaml` defines a Docker web service named
`predict-with-fun`.

1. Push the repository to GitHub.
2. In Render, create a new Blueprint.
3. Connect `exitLQ/predict_withFun`.
4. Add the desired provider keys as secret environment variables.
5. Deploy the Blueprint.
6. Confirm that `/api/health` returns `status: ok`.

The Blueprint already configures the default models, cache TTL, provider
fallback, and health-check path. API keys use `sync: false` and must be entered
in Render.

Do not put real keys in `render.yaml`, `.env.example`, source code, GitHub
Actions logs, screenshots, or issues.

### Production considerations

The current cache and rate limiter are held in process memory. For horizontal
scaling, use a shared cache and limiter. Also consider:

- HTTPS at the reverse proxy;
- trusted proxy and client-IP configuration;
- centralized logging and error monitoring;
- explicit resource and spend limits;
- a persistent analysis-history database;
- regular dependency and model-version reviews.

## Architecture

```text
.
├── .env.example             # Local configuration template
├── .github/
│   └── workflows/           # GitHub Actions CI
├── app.py                   # FastAPI routes, limits, and static delivery
├── database.py              # PostgreSQL/SQLite analysis persistence
├── models.py                # Pydantic request and response models
├── openai_analyzer.py       # All AI providers, cache, fallback, and costs
├── polymarket_client.py     # Polymarket API access, parsing, and data cache
├── static/
│   ├── index.html           # Application markup
│   ├── app.js               # Browser state, API calls, and rendering
│   └── style.css            # Responsive visual design
├── tests/                   # Automated test suite
├── synthesis.py             # Provider consensus and weighting
├── Dockerfile               # Production container image
├── render.yaml              # Render Blueprint
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development and test dependencies
└── pyproject.toml           # Ruff and pytest configuration
```

### Backend responsibilities

`app.py`:

- serves the frontend;
- validates route parameters;
- applies analysis request limits;
- loads Polymarket data outside the async event loop;
- runs provider comparisons concurrently;
- maps domain errors to HTTP responses.

`database.py`:

- creates the portable analysis-history schema;
- uses PostgreSQL in production and SQLite locally;
- stores validated result JSON and searchable metadata;
- lists saved analyses and restores complete results.

`polymarket_client.py`:

- accesses Polymarket endpoints;
- normalizes external response fields;
- parses outcomes and prices;
- selects and sorts active markets;
- fetches price history;
- detects unambiguous first-outcome resolutions;
- maintains the short-lived market-data cache.

`openai_analyzer.py`:

- builds provider prompts;
- invokes OpenAI, xAI, or Anthropic;
- validates structured output;
- normalizes assessments;
- extracts source links;
- calculates usage and estimated cost;
- caches analysis results;
- applies provider fallback.

`synthesis.py`:

- derives provider weights from resolved forecast accuracy;
- aggregates provider estimates without another API request;
- classifies disagreement and consensus valuation;
- combines unique provider risks.

### Frontend responsibilities

The frontend uses browser-native APIs only. It:

- maintains the selected category and markets;
- renders market and analysis cards;
- sends provider and comparison requests;
- draws price-history charts on `<canvas>`;
- persists the watchlist locally;
- creates client-side CSV and JSON downloads;
- renders untrusted external text with `textContent`.

## Security and privacy

- Provider secrets stay in backend environment variables.
- `.env` is excluded from version control.
- The public health endpoint exposes only whether a key exists.
- Query parameters are validated by FastAPI.
- Pydantic validates outbound API data.
- AI analysis requests are rate limited.
- External strings and AI output are inserted as text rather than executable HTML.
- External links use `noopener noreferrer`.
- The production container runs without root privileges.
- No application user account, personal profile, or server-side watchlist is stored.

Polymarket descriptions and search results are untrusted external content.
Provider system instructions tell models to analyze objectively, but model
output must still be treated as untrusted and fallible.

If a key is accidentally committed:

1. Revoke it immediately in the provider console.
2. Create a replacement key.
3. Remove the secret from Git history if necessary.
4. Update deployment secrets.
5. Review provider usage for unauthorized requests.

## Troubleshooting

### The application says “AI key missing”

Add at least one valid provider key to `.env` and restart the server. Verify
configuration with `/api/health`.

### The application remains in demo mode

Demo mode is reported by the health endpoint only when none of the three keys
is present. Check variable names and restart the process after changing `.env`.

### A different provider produced the result

Automatic fallback was used. Check `requested_provider`, `research_provider`,
and `fallback_used` in the response. Disable fallback with:

```text
PROVIDER_FALLBACK=false
```

### A repeated analysis has zero new cost

This is expected for a cache hit. The result shows `cached: true`. Wait for the
TTL, restart the process, change the market probabilities, or temporarily use
a shorter `ANALYSIS_CACHE_TTL`.

### Provider comparison shows fewer than three results

Live comparison uses only configured providers. A provider may also have
returned an error; inspect the `errors` object or the error notice in the
interface.

### `429 Analysis limit reached`

The client has reached `ANALYSIS_REQUESTS_PER_HOUR`. Wait for the sliding
one-hour window or adjust the limit for your deployment.

### Provider returns `503`

Common causes include an invalid key, missing model access, rate limiting,
temporary provider downtime, an unsupported replacement model, or disabled
fallback with no working selected provider.

### Categories or markets return `502`

Polymarket may be unavailable or may have changed an upstream response. Retry
later and inspect the application logs.

### Price history is empty

The market may not expose a usable first-outcome token ID, or Polymarket may
not have history for the selected interval.

### Cost estimate looks incorrect

Confirm the selected model and update the matching `*_USD_PER_MTOK` and
`*_SEARCH_USD_PER_1K` values. The estimate cannot reproduce every provider
billing rule.

### GitHub Actions fails

Open the failed run, expand the Ruff or pytest step, reproduce it locally, and
push the correction:

```bash
ruff check .
python -m pytest -vv
```

## Known limitations

- AI estimates can be wrong, stale, biased, or based on incomplete sources.
- Source extraction depends on provider response formats.
- Cost reporting is approximate.
- Cache and rate-limit state are not shared across processes.
- There is no authentication or user-specific server-side storage.
- Watchlists exist only in the current browser.
- Database migrations are currently additive and initialized by application code.
- Provider comparison can increase API spend.
- Category analysis is capped at ten markets.
- Single-market lookup loads up to 100 category markets before matching a slug.
- The first listed outcome is used for probability analysis and price history.

## License

No license file is currently included. Unless a license is added, copyright
law applies by default even though the repository is public.

<!-- hypertribe:sponsors:start -->
## Sponsors

[![predict_withFun Sponsors](https://api.tribe.run/tokens/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU/sponsors.svg)](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU)

Become a sponsor on [Tribe.run](https://tribe.run/token/2jEmNDmZF8m8nttfr1GJYU2qgFmRgFSSV7cUiwYiqhbU).
<!-- hypertribe:sponsors:end -->
