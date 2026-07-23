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
- [Redis and background jobs](#redis-and-background-jobs)
- [Persistent analysis history](#persistent-analysis-history)
- [Database migrations](#database-migrations)
- [Admin dashboard](#admin-dashboard)
- [Accuracy tracking](#accuracy-tracking)
- [Automatic resolution sync](#automatic-resolution-sync)
- [Calibration diagrams](#calibration-diagrams)
- [Provider synthesis](#provider-synthesis)
- [Source quality assessment](#source-quality-assessment)
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
- Shares cache entries, rate limits, and job status through Redis when configured
- Runs provider comparisons and resolution checks as pollable background jobs
- Provides a token-protected operations dashboard for cost, cache, jobs, and provider health
- Shows whether a result came from the cache
- Reports input tokens, output tokens, and detected search calls
- Calculates an estimated USD cost for each new analysis
- Applies a configurable per-client analysis limit
- Caches Polymarket data for five minutes
- Stores completed live analyses in PostgreSQL or local SQLite
- Scores resolved forecasts with Brier score and compares AI with the market
- Builds an accuracy-weighted consensus from provider comparison results
- Normalizes, deduplicates, classifies, and ranks research sources

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

### Reopen a saved analysis

The **Analysis history** section loads the newest stored live analyses. Search
by category, filter by OpenAI, Grok, or Claude, and choose whether to load 10,
25, 50, or 100 records. Select **Open result** to restore the complete original
summary, probabilities, reasoning, risks, sources, usage, and provider
metadata in the normal analysis panel. The list refreshes automatically after
a new analysis and can also be refreshed manually.

Demo output and cache hits are not stored, so they do not appear in this list.
Filters run in the browser over the selected record limit; they do not make
additional provider calls or incur AI cost.

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
python migrate.py
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
| `ADMIN_TOKEN` | `change-me` | Bearer token that protects admin metrics; required in production |
| `HOST` | `0.0.0.0` | Bind address when running `python app.py` |
| `PORT` | `8000` | HTTP port |
| `DATABASE_URL` | `sqlite:///./predict_withfun.db` | PostgreSQL or SQLite connection URL |
| `REDIS_URL` | — | Redis-compatible URL for shared infrastructure |
| `BACKGROUND_QUEUE` | `local` | `local` thread jobs or external `rq` workers |
| `LOCAL_JOB_WORKERS` | `3` | Maximum local background-job threads |
| `JOB_TIMEOUT` | `600` | RQ job timeout in seconds |
| `JOB_RESULT_TTL` | `3600` | Shared job-result lifetime in seconds |
| `AUTO_RESOLUTION_LIMIT` | `500` | Default unresolved-market limit for the scheduled CLI job |

Boolean values are enabled only when their value is `true`, ignoring letter
case.

## Admin dashboard

The **Admin dashboard** section reports operational information without
exposing API keys, prompts, source contents, Redis URLs, or database URLs. Enter
the `ADMIN_TOKEN` and select **Load dashboard** to view:

- durable stored-analysis counts, forecast counts, and estimated provider cost;
- process-local request, cache-hit, rate-limit, and background-job counters;
- provider call success, failure, and average latency;
- database availability and Redis/background-queue state.

The browser keeps the token in `sessionStorage`, so it is removed when the tab
session ends and is never persisted in `localStorage`. In production
(`ENVIRONMENT=production`), the endpoint returns `503` until `ADMIN_TOKEN` is
configured. An absent or incorrect bearer token returns `401`. Development
allows token-free access only when no token is configured.

Runtime counters are intentionally lightweight and process-local. They reset
after a restart and are not combined across multiple web workers. Stored
history and estimated cost come from the database and remain durable.

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

The analysis cache uses Redis when `REDIS_URL` is configured and falls back to
an in-memory dictionary otherwise. Its key includes:

- selected provider;
- category name;
- market slugs;
- current first-outcome probabilities.

The default time to live is 1,800 seconds. A cache hit returns `cached: true`,
preserves the original token counts for transparency, and reports zero new
estimated API cost.

Important cache properties:

- The local fallback cache is cleared whenever the process restarts.
- Redis-backed entries are shared across application instances.
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

The limiter uses an atomic Redis sorted-set operation when Redis is available.
Without Redis it falls back to the original process-local sliding window.

## Redis and background jobs

Redis is optional locally and recommended for multi-instance deployments. It
provides:

- shared analysis-cache entries;
- shared per-IP sliding-window request limits;
- background-job status and results that any web instance can poll.

Provider comparisons and resolution checks are submitted through job
endpoints. The API immediately returns a job ID, and the browser polls
`GET /api/jobs/{job_id}` until the job finishes or fails.

| Mode | Behavior |
| --- | --- |
| `BACKGROUND_QUEUE=local` | A bounded thread pool runs jobs in the web process; Redis shares status when configured |
| `BACKGROUND_QUEUE=rq` | Jobs enter the `predict_with_fun` Redis queue for separate workers |

Local mode requires no additional process and is the default. Jobs can be lost
if the web process restarts. RQ mode provides worker isolation and requires
`REDIS_URL` plus at least one continuously running worker:

```bash
rq worker predict_with_fun
```

Run Redis locally with Docker:

```bash
docker run --rm -p 6379:6379 redis:latest
```

Then set:

```text
REDIS_URL=redis://localhost:6379/0
```

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

The web interface exposes the same history through a responsive archive with
category search, provider filtering, selectable record limits, localized
timestamps, cost and market-count metadata, and a full saved-result view.

## Database migrations

Database schema changes are versioned with Alembic. The migration history lives
in `migrations/versions/`; revision `0001` defines the analysis-history and
forecast-scoring tables plus their indexes.

Apply all pending migrations:

```bash
python migrate.py
```

Equivalent Alembic command:

```bash
alembic upgrade head
```

Inspect the current database revision:

```bash
alembic current
```

Create a migration after changing the schema:

```bash
alembic revision -m "Describe the schema change"
```

Every migration must provide both `upgrade()` and `downgrade()`, remain
compatible with PostgreSQL and SQLite, and be reviewed before deployment. The
initial migration safely detects tables created by older predict_withFun
versions, adds missing indexes, and then establishes Alembic's revision marker.

Database access lazily applies pending migrations once per configured database
URL as a safety net. The Docker entrypoint explicitly runs migrations before
starting Uvicorn, which remains the recommended production sequence.

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

## Automatic resolution sync

`resolution_sync.py` provides a one-shot command for scheduled environments:

```bash
python resolution_sync.py --limit 500
```

It selects at most the requested number of distinct unresolved market slugs,
checks each against Polymarket, scores only unambiguous closed markets, prints
a machine-readable JSON summary, and exits. The limit must be between 1 and
1,000; when omitted, `AUTO_RESOLUTION_LIMIT` is used.

The operation is idempotent at the database level: forecast rows are updated
only while their outcome is still `NULL`. Repeating a run does not rescore
already resolved forecasts. Individual upstream Polymarket errors are skipped
so one unavailable market does not abort the full batch.

The Render Blueprint creates `predict-with-fun-resolution-sync`, a Docker cron
job scheduled for `03:17 UTC` every day (`17 3 * * *`). It shares the production
PostgreSQL database but does not require provider API keys or Redis. Render
guarantees at most one active run for a given cron job. The scheduler remains
external to the web process, preventing duplicate scheduled work when the web
service scales to multiple instances.

For another platform, schedule the same terminating command with its native
cron or task scheduler and provide `DATABASE_URL`. You can still trigger the
existing manual UI/API sync independently.

## Calibration diagrams

The accuracy section includes one reliability diagram for each provider with
resolved forecasts. Predictions are grouped into ten probability intervals.
Each plotted point compares the interval's mean predicted probability on the
horizontal axis with its observed positive-outcome frequency on the vertical
axis. A perfectly calibrated provider follows the dashed diagonal.

Point size grows with the number of forecasts in that interval. Every chart
also includes a text list with the interval, observed frequency, and sample
count, so the information does not depend on color or pointer interaction.
Empty intervals are omitted.

The displayed expected calibration error (ECE) is the forecast-count-weighted
mean absolute difference between predicted and observed probability across
populated intervals. Lower is better, but small samples can produce unstable
diagrams and ECE values. Calibration measures probability reliability; it does
not replace Brier score, source review, or comparison with the market baseline.

The API accepts between 5 and 20 bins. The interface uses 10 to balance detail
and sample size. Resolution synchronization refreshes both accuracy cards and
calibration diagrams.

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

## Source quality assessment

Extracted research URLs pass through a deterministic quality pipeline before
they are returned:

1. host names are normalized to lowercase and `www.` is removed;
2. URL fragments and common tracking parameters are removed;
3. canonical URLs are deduplicated;
4. domains are assigned a source category;
5. each source receives a quality level, numeric score, and explanation;
6. sources are sorted by score and limited to the best 12.

Supported categories are `government`, `academic`, `official`, `news`,
`social`, and `other`.

| Source type | Default score | Quality |
| --- | ---: | --- |
| Government domain | `0.95` | High |
| Academic domain | `0.90` | High |
| Recognized international institution | `0.90` | High |
| Established news domain | `0.80` | High |
| Official-looking title on an unlisted domain | `0.70` | Medium |
| General web source | `0.50` | Medium |
| Social platform | `0.35` | Low |

The frontend shows category, domain, quality, and score. Hovering over the
quality badge displays the rule-based explanation.

This score is a review aid, not a factuality guarantee. Domain reputation
cannot prove that an individual article is correct, current, independent, or
relevant. Social sources are ranked lower because they require corroboration,
not because every social post is false. The allowlists are intentionally small
and can be reviewed in `source_quality.py`.

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

### `GET /api/admin/metrics`

Returns the protected operations snapshot. It never returns secrets,
connection URLs, prompt text, or research content.

```bash
curl \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/admin/metrics
```

The response includes `database_available`, Redis and queue state, durable
analysis/cost totals, process-local cache and job counters, and per-provider
call metrics.

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

The synchronous endpoint remains available for API compatibility. The browser
uses the background endpoint for comparisons.

### `POST /api/jobs/compare`

Queues a comparison and returns a job ID with status `queued`.

```bash
curl -X POST \
  "http://localhost:8000/api/jobs/compare?category_id=1&limit=5"
```

### `POST /api/jobs/accuracy-sync`

Queues a resolution check.

```bash
curl -X POST \
  "http://localhost:8000/api/jobs/accuracy-sync?limit=100"
```

### `GET /api/jobs/{job_id}`

Returns `queued`, `running`, `finished`, or `failed`. Successful job output is
stored in `result`; failed jobs expose `error`.

```json
{
  "id": "8db66d3e-...",
  "status": "finished",
  "result": {
    "checked_markets": 25,
    "newly_resolved_markets": 2,
    "scored_forecasts": 6
  },
  "error": null
}
```

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

### `GET /api/accuracy/calibration`

Returns populated calibration bins, resolved sample count, and expected
calibration error for every provider with resolved forecasts. The optional
`bins` parameter defaults to `10` and accepts values from 5 to 20.

```bash
curl "http://localhost:8000/api/accuracy/calibration?bins=10"
```

Each bin contains `lower_bound`, `upper_bound`, `mean_probability`,
`observed_frequency`, and `forecast_count`.

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

Each source includes its canonical URL, domain, category, quality level,
numeric quality score, and a human-readable scoring explanation.

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
- usage and cost calculation;
- persistent history round trips and skipped demo/cache records;
- resolution parsing, Brier scoring, and provider accuracy summaries;
- scheduled resolution CLI argument validation and JSON output;
- provider weighting, consensus probabilities, and disagreement classification;
- URL canonicalization, deduplication, source classification, and ranking.
- Redis-backed cache/status operations and local background-job completion.

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
`predict-with-fun` and a daily Docker cron job named
`predict-with-fun-resolution-sync`.

1. Push the repository to GitHub.
2. In Render, create a new Blueprint.
3. Connect `exitLQ/predict_withFun`.
4. Add the desired provider keys as secret environment variables.
5. Deploy the Blueprint.
6. Confirm that `/api/health` returns `status: ok`.

The Blueprint configures PostgreSQL, a private Render Key Value instance,
default models, cache TTL, provider fallback, the health-check path, and the
daily resolution run at `03:17 UTC`. API keys use `sync: false` and must be
entered in Render. Render cron jobs are paid services (currently with a minimum
monthly charge), so review the current Render pricing before applying the
Blueprint. Remove the `type: cron` block if you prefer another scheduler.

The Blueprint uses local background threads so it can remain on the free web
plan. For isolated RQ execution, create a Render background worker with the
same repository and environment, set `BACKGROUND_QUEUE=rq` on the web service,
and use this worker start command:

```bash
rq worker predict_with_fun
```

Render background workers do not offer a free instance type, so this optional
paid resource is deliberately not created automatically by `render.yaml`.

Do not put real keys in `render.yaml`, `.env.example`, source code, GitHub
Actions logs, screenshots, or issues.

### Production considerations

Configure Redis for horizontal scaling so cache, rate limits, and job status
are shared. Also consider:

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
├── infrastructure.py        # Redis cache, limits, and shared job status
├── job_queue.py             # Local and RQ background-job adapter
├── job_tasks.py             # Importable background task functions
├── models.py                # Pydantic request and response models
├── migrate.py               # Programmatic Alembic upgrade command
├── migrations/              # Versioned database schema changes
├── openai_analyzer.py       # All AI providers, cache, fallback, and costs
├── operations.py            # Thread-safe process runtime metrics
├── polymarket_client.py     # Polymarket API access, parsing, and data cache
├── resolution_sync.py       # One-shot automatic resolution CLI
├── source_quality.py        # Source normalization and quality rules
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

`migrate.py` and `migrations/`:

- configure Alembic from `DATABASE_URL`;
- upgrade SQLite and PostgreSQL through the same revision chain;
- baseline databases created by older application versions;
- provide reversible, reviewable schema evolution.

`infrastructure.py`:

- creates the optional Redis connection;
- reads and writes shared cache entries;
- applies distributed rate limits;
- stores expiring job status and results.

`operations.py`:

- records process-local cache, provider, request, and job counters;
- calculates cache-hit rate and provider average latency;
- exposes only aggregated, non-sensitive operational data.

`job_queue.py` and `job_tasks.py`:

- submit work to local threads or RQ;
- expose consistent job-state responses;
- run comparisons and resolution checks outside request handling;
- preserve synchronous endpoints for direct API clients.

`resolution_sync.py`:

- validates the scheduled batch limit;
- invokes the same resolution logic used by the API and background jobs;
- prints a stable JSON run summary and terminates for cron execution.

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

`source_quality.py`:

- removes common URL tracking data;
- canonicalizes source URLs for deduplication;
- classifies recognized domain types;
- assigns transparent quality scores and explanations.

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

### A background job stays queued

With `BACKGROUND_QUEUE=rq`, verify that `REDIS_URL` is reachable and an RQ
worker is running on the `predict_with_fun` queue. Use
`BACKGROUND_QUEUE=local` when no external worker is available.

### Redis is unavailable

The application degrades to local cache, rate limiting, and background threads.
Check `/api/health`, the Redis URL, network policy, and Redis service status.

### Admin dashboard returns `401` or `503`

`401` means the bearer token is absent or does not match `ADMIN_TOKEN`. `503`
in production means `ADMIN_TOKEN` has not been configured. Add the secret to
the deployment, restart the service, and load the dashboard with the same
token. Do not place the token in source control or a public URL.

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
- Local fallback cache, rate limits, and jobs are process-specific without Redis.
- Local background jobs do not survive process restarts.
- RQ mode requires a separately operated worker.
- There is no authentication or user-specific server-side storage.
- Watchlists exist only in the current browser.
- Migrations must be applied before running standalone RQ workers against a new database.
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
