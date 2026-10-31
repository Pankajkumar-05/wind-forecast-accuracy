# Wind Forecast Accuracy — Day-Ahead Purchasing Dashboard

A web app that helps a UK energy utility's day-ahead buying team answer two questions about national wind generation:

1. **What was the latest wind forecast available when the day-ahead purchase decision had to be made?**
2. **How accurate have those forecasts been?**

It uses real, public **Elexon BMRS** data (no API key needed) and is restricted to **purchase decisions taken in January 2026**.

> **Deployed app:** `TODO: add the Vercel / Heroku URL here after deploying`
> **Demo video:** `TODO: add the unlisted YouTube URL here`

---

## Contents

1. [Key features](#key-features)
2. [How it works (architecture)](#how-it-works-architecture)
3. [Forecast-selection methodology](#forecast-selection-methodology) ← the most important part
4. [Metric definitions](#metric-definitions)
5. [Assumptions](#assumptions)
6. [Directory structure](#directory-structure)
7. [Run it locally](#run-it-locally)
8. [Run with Docker](#run-with-docker)
9. [Tests](#tests)
10. [API endpoints](#api-endpoints)
11. [Environment variables](#environment-variables)
12. [Deployment](#deployment)
13. [Edge cases handled](#edge-cases-handled)
14. [AI assistance](#ai-assistance)
15. [Limitations](#limitations)
16. [Future improvements](#future-improvements)

---

## Key features

- **Latest decision-time forecast** — for a delivery day: average/peak/lowest forecast (MW), when it was published, the decision cutoff that applied, and (if available) what actually happened.
- **Forecast vs actual chart** — interactive time series for the whole month, with hover tooltips (forecast, actual, error, and when that forecast was published), a legend, and UK-local timestamps.
- **Forecast error** — signed error and absolute error per forecast period, an error-over-time chart, and a day-by-day table.
- **KPIs** — MAE, RMSE, bias, MAPE and the number of forecast periods evaluated, each with a plain-English explanation.
- **Date filter** — presets (full period, last 14 / 7 days, last day) plus a custom range.
- **Data-quality panel** — always shows how complete the data is (missing forecasts/actuals, late forecasts excluded, duplicates removed, malformed rows skipped). Nothing is dropped silently.
- Loading, empty and error states with retry; responsive layout; light and dark mode.

## How it works (architecture)

```
Browser (React + TypeScript, Recharts)
   │  GET /api/...        (same origin; nginx / Vite dev server proxies to the backend)
   ▼
FastAPI backend ── routes (thin) ──▶ AnalysisService ──▶ ElexonClient ──▶ Elexon BMRS API
                                         │                (async httpx, chunked, retries)
                                         ▼
                      parsing → forecast selection → matching → metrics   (pure functions)
```

- The backend loads the whole configured window (~1,500 half-hourly actuals and ~750 hourly forecast periods) **once**, cleans it, and keeps it in an in-memory cache (TTL 1 h). Every endpoint and every date filter is answered from that cache, so the Elexon API is not called once per widget or per click. Concurrent first requests share a single in-flight load.
- Date ranges are split into small chunks which are fetched **concurrently** (async I/O is genuinely useful here), with bounded concurrency and retry with exponential backoff on timeouts / 429 / 5xx.
- If any chunk still fails, the request fails with a clear `502`. **It never returns a partial month as if it were complete.**
- All business logic lives in pure, easily tested functions (`backend/app/services/`); routes only validate input and call the service.

**Stack:** React 18 + TypeScript + Vite + Recharts · Python 3.12+ · FastAPI + Pydantic v2 + httpx · pytest · Vitest + Testing Library · Docker / Docker Compose · Vercel.

## Forecast-selection methodology

**The problem.** The Elexon `WINDFOR` dataset contains *many* forecasts for the same target period. Each row has:

- `startTime` — the period being forecast (the *delivery* time), and
- `publishTime` — when that forecast was *created*.

A forecast for 14:00 tomorrow is re-published again and again, all the way up to delivery. A buyer deciding on the day before can only use forecasts that already existed. Using "the latest forecast" (or an average) would quietly use information the buyer did not have and make the forecasts look better than they were.

**The rule** (in `backend/app/core/decision_rule.py`):

> For a forecast period delivered on day **D**, the decision cutoff is **D − 1 day at 09:00 UK time**. We use the forecast with the **latest `publishTime` that is ≤ the cutoff**. Forecasts published after the cutoff are never used.

Example, for delivery on 15 Jan at 12:00: cutoff = 14 Jan 09:00. A forecast published 14 Jan 08:30 is used; one published 14 Jan 09:30 or 15 Jan 06:00 is ignored.

**Scope — "decisions made in January 2026".** A decision taken on D − 1 covers delivery day D. So decisions taken 1–31 January 2026 cover delivery days **2 January – 1 February 2026**. That is the configured window (`DELIVERY_WINDOW_START` / `_END`).

**Details**
- The cutoff is applied **per delivery day**, using the UK local calendar day (so it stays correct across clock changes).
- A forecast published exactly *at* the cutoff is allowed (`<=`).
- Exact duplicates (same `startTime` + `publishTime`) are collapsed.
- Forecast periods that only have late forecasts get **no forecast** — they are reported as missing, never guessed.
- Errors are computed only for forecast periods that have **both** a decision-time forecast and an actual; the counts of everything else are shown to the user.

## Time grids: live evidence vs assumptions

**Live Elexon evidence** (reported by the author from running the probe/verification scripts against the live API for the full January decision window; it was **not** re-run in the build sandbox, which cannot reach Elexon):

| Observation | Value |
|---|---|
| `WINDFOR` unique target (`startTime`) timestamps | 744 (= 31 days × 24) |
| `FUELHH` unique timestamps | 1,488 (30-minute resolution) |
| Exact intersection | 744 |
| `WINDFOR` timestamps with no `FUELHH` match | 0 |
| `FUELHH` timestamps with no `WINDFOR` match | 744, **all at minute `:30`** |
| `WINDFOR` `startTime` minute-of-hour | `:00` only; consecutive targets are 60 minutes apart |

So an earlier "744 of 1,488 half-hours (50 %)" reading was a **resolution mismatch, not missing forecasts**.

**How the dashboard treats this**
- Each `WINDFOR` forecast is compared with the `FUELHH` actual that has **exactly the same `startTime`**. Nothing is interpolated, forward-filled, duplicated or averaged: neither the hourly forecast into the `:30` periods, nor the two half-hourly actuals into an hour.
- Accuracy metrics (MAE, RMSE, bias, MAPE, P90) use only those exact matches. The metric formulas are unchanged by the coverage fix.
- The `:30` actual periods are actual periods **for which no forecast exists**. They are shown as information ("Actual periods with no forecast"), are not "missing forecasts", and do not raise a data warning.
- **Coverage is forecast-grid coverage**: matched periods ÷ expected forecast periods (e.g. 744 / 744), not ÷ 1,488.
- `FORECAST_RESOLUTION_MINUTES` (default 60) only defines the expected forecast grid for that denominator. If a forecast ever appears off that grid it is still matched exactly and a warning is shown.

**Assumptions (not Elexon facts)**
- The decision cutoff (D − 1, 09:00 Europe/London) and the 2 Jan – 1 Feb delivery window (see [Assumptions](#assumptions)).
- `FORECAST_RESOLUTION_MINUTES=60` is chosen because the live data above is hourly.
- **What an hourly `WINDFOR` value represents is not stated by the Elexon sources I could find**: it may be an instantaneous value at the start of the hour or an hour average. This project makes **no claim either way**; it simply compares the published value with the `FUELHH` actual for the same `startTime`. If the value is an hour average, comparing it with a single half-hour actual adds some unavoidable noise. Confirm with Elexon before presenting a stronger interpretation.

## Metric definitions

Sign convention everywhere: **error = forecast − actual**.

| Metric | Formula | Meaning |
|---|---|---|
| Signed error | `forecast − actual` | Positive = forecast too high (buyer under-buys other power). Negative = too low (buyer over-buys). |
| Absolute error | `abs(forecast − actual)` | Size of the miss, ignoring direction. |
| **MAE** | mean of absolute errors | The typical miss, in MW. |
| **RMSE** | √ mean of squared errors | Like MAE but big misses count more. RMSE ≫ MAE means occasional large surprises. |
| **Bias** (mean error) | mean of signed errors | Whether forecasts lean high or low on average. Errors can cancel out, so bias can be ~0 while MAE is large. |
| **MAPE** | mean of `abs(error) / actual × 100` | Error as a % of actual output. |
| MAE % of mean actual | MAE ÷ mean actual | Scale-free way to read MAE. |
| P90 abs. error | 90th percentile of absolute error | "90% of forecast periods were missed by less than this." |

**MAPE and zero wind.** Wind output can be zero or tiny, where a percentage is meaningless (or a division by zero). Forecast periods with actual generation below `MAPE_MIN_ACTUAL_MW` (default **50 MW**) are **excluded from MAPE only**; the UI states how many were excluded. They still count in MAE / RMSE / bias. If every actual is below the floor, MAPE is `null` (shown as "—"), never `inf` or `0`.

## Assumptions

1. **Decision cutoff = D − 1 at 09:00 UK time.** The brief says decisions are made "one day before the delivery day" but gives no exact gate-closure time, so this is an explicit, configurable assumption — **not** a claimed market fact. 09:00 was chosen as a deliberately conservative time on the morning before delivery (GB day-ahead auctions close in the morning of D − 1; **please verify the exact gate-closure time you want to present** and change `DECISION_CUTOFF_TIME` if needed — no code change required, and the UI/README text follow the setting).
2. **"January 2026" = decisions taken in January**, i.e. delivery days 2 Jan – 1 Feb (see above). Change `DELIVERY_WINDOW_START/END` to use a different reading.
3. Elexon timestamps are UTC; they are normalised to UTC internally and shown in **UK local time** in the UI.
4. `FUELHH` is half-hourly at national level and `WINDFOR` targets are hourly (live-verified, see [Time grids](#time-grids-live-evidence-vs-assumptions)). The two are **not** resampled to a common grid: only exact timestamp matches are evaluated.
5. Where Elexon returns several actual values for one timestamp, the most recently published wins.

## Directory structure

```
.
├── README.md
├── docker-compose.yml            # backend + frontend (nginx) for local use
├── .env.example                  # optional overrides for docker compose
├── .gitignore
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory, error handlers, CORS
│   │   ├── api/routes.py         # HTTP routes (thin)
│   │   ├── schemas/api.py        # Pydantic response models (the API contract)
│   │   ├── models/domain.py      # immutable domain objects
│   │   ├── core/
│   │   │   ├── config.py         # settings from environment variables
│   │   │   ├── decision_rule.py  # ★ the decision-time cutoff business rule
│   │   │   ├── errors.py         # domain exceptions
│   │   │   └── logging.py
│   │   ├── services/
│   │   │   ├── elexon_client.py  # async Elexon client: chunking, retries, optional disk cache
│   │   │   ├── parsing.py        # raw JSON → validated records (counts bad rows)
│   │   │   ├── forecast_selection.py  # ★ picks the decision-time forecast; de-duplication
│   │   │   ├── comparison.py     # matches forecast ↔ actual, computes errors + coverage
│   │   │   ├── metrics.py        # MAE, RMSE, bias, MAPE, percentiles, daily metrics
│   │   │   └── analysis_service.py  # orchestration + in-memory cache
│   │   └── utils/                # time helpers, caches
│   ├── tests/                    # pytest suite (107 tests, no network needed)
│   ├── scripts/probe_elexon.py   # check the live Elexon API from your machine
│   ├── index.py                  # Vercel entry point
│   ├── Dockerfile  Procfile  requirements*.txt  .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/DashboardPage.tsx   # composes the dashboard, handles per-section states
│   │   ├── components/               # KPI grid, charts, tables, filter, data-quality panel…
│   │   ├── hooks/useAsync.ts         # loading/error/retry + request cancellation
│   │   ├── services/api.ts           # typed API client
│   │   ├── types/api.ts              # API types (mirror backend schemas)
│   │   ├── utils/format.ts           # number/date formatting (UK time)
│   │   └── test/fixtures.ts          # test data
│   ├── Dockerfile  nginx.conf  .env.example  vite.config.ts
```

## Run it locally

Requirements: Python 3.12+, Node 20+.

**Backend** (terminal 1)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/probe_elexon.py       # optional but recommended: confirms the live Elexon API works
uvicorn app.main:app --reload --port 8000
```
API docs: <http://localhost:8000/docs>

**Frontend** (terminal 2)
```bash
cd frontend
npm install
npm run dev
```
Open <http://localhost:5173>. The dev server proxies `/api` to `http://localhost:8000`.

The first load fetches a month of data from Elexon (a few seconds); after that everything is served from the backend's cache.

## Run with Docker

```bash
docker compose up --build
```
- Dashboard: <http://localhost:8080> (nginx serves the React build and proxies `/api` to the backend)
- API + docs: <http://localhost:8000/docs>

Stop with `Ctrl+C` / `docker compose down`. Raw Elexon responses for fully historical periods are cached in a Docker volume, so restarts are fast. To change settings, copy `.env.example` to `.env`.

## Tests

```bash
# Backend (107 tests)
cd backend && source .venv/bin/activate && pytest

# Frontend (35 tests) + type-check + production build
cd frontend && npm test && npm run typecheck && npm run build
```

The backend tests use a **fake Elexon served through `httpx.MockTransport`**, so they are fast, deterministic and never touch the network. They cover the business rules rather than just plumbing:

- **Forecast selection:** latest-before-cutoff wins; late forecasts never used; exactly-at-cutoff allowed; only-late → no forecast; duplicates; per-day cutoff; out-of-window rows; summer-time conversion.
- **Matching:** exact join on `startTime` with an hourly-WINDFOR / half-hourly-FUELHH fixture (no forward-fill; `:30` actuals never change any metric), signed/absolute error, missing forecast/actual reported (not dropped), mismatched timestamps, 23- and 25-hour clock-change days, forecast-grid coverage (`:30` actuals are not "missing forecasts").
- **Metrics:** MAE/RMSE/bias on hand-computed values, RMSE ≥ MAE, cancelling errors, empty input → `None`, MAPE with zero/near-zero actuals, percentile.
- **Parsing:** non-WIND ignored, malformed rows counted, zero is valid.
- **Client:** correct query parameters, chunking, retry on 5xx, no retry on 4xx, persistent failure raises (no partial data), bad JSON, disk cache.
- **API:** end-to-end responses, caching (one Elexon load serves all endpoints), date validation (`422`), Elexon outage (`502`) and recovery, empty data, configurable cutoff.

Frontend tests cover formatting, the date-filter validation, KPI rendering (including "no data" → dashes and the MAPE exclusion note), the data-quality panel, and the page's loading / error + retry / empty / partial-failure states with a mocked API.

## API endpoints

| Method & path | Description |
|---|---|
| `GET /api/health` | Liveness check (does not call Elexon). |
| `GET /api/config` | Active window and the decision-time rule (the UI uses this to explain itself). |
| `GET /api/forecasts/latest?delivery_date=` | Decision-time forecast for one delivery day (default: the latest day that has one). `404` if none. |
| `GET /api/forecasts?start=&end=` | Decision-time forecast for each forecast period, with publish time and lead time. |
| `GET /api/actuals?start=&end=` | Actual WIND generation per FUELHH period (every 30 minutes). |
| `GET /api/comparison?start=&end=` | Matched forecast/actual points with per-period errors, plus a data-quality summary. |
| `GET /api/metrics?start=&end=` | MAE, RMSE, bias, MAPE…, overall and per delivery day, plus data quality. |

`start` / `end` are UK-local delivery days (`YYYY-MM-DD`), default to the full window. Errors: `422` invalid/out-of-scope dates, `404` no data, `502` Elexon unavailable or malformed.

## Environment variables

No secrets are needed — the Elexon API is public. Full list with defaults: [`backend/.env.example`](backend/.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `DECISION_CUTOFF_TIME` | `09:00` | Time of day (decision timezone) when the day-ahead decision is assumed to be made. |
| `DECISION_TIMEZONE` | `Europe/London` | Timezone for the cutoff and for what counts as a "delivery day". |
| `DECISION_DAYS_AHEAD` | `1` | Days before delivery that the decision is made. |
| `DELIVERY_WINDOW_START` / `_END` | `2026-01-02` / `2026-02-01` | Delivery days in scope. |
| `MAPE_MIN_ACTUAL_MW` | `50` | MAPE ignores forecast periods with less wind than this. |
| `FORECAST_RESOLUTION_MINUTES` | `60` | Spacing of the expected forecast grid (positive multiple of 30). Used **only** for the coverage denominator; it never creates, fills or moves a forecast. |
| `REQUEST_CHUNK_DAYS` | `3` | Days per Elexon request. |
| `CACHE_TTL_SECONDS` | `3600` | In-memory cache lifetime. |
| `CACHE_DIR` | *(empty)* | Optional on-disk cache for historical Elexon responses. |
| `CORS_ORIGINS` | localhost dev origins | Needed only when frontend and backend are on different domains. |
| `VITE_API_BASE_URL` (frontend) | *(empty)* | Backend URL when it is on a different domain. |

## Deployment

**Choice: Vercel**, as two projects from the same repo. The frontend is a plain static Vite app and the backend is a FastAPI app with a Vercel-compatible entry point (`backend/index.py`). Vercel is the simplest fit because both halves deploy with essentially zero configuration. Heroku also works for the backend (a `Procfile` is included), but needs a second hosting choice for the static frontend.

> ⚠️ **Not yet deployed or tested on Vercel.** The development sandbox could not reach Vercel, so deployment is *prepared* but not performed. Follow the steps below, then paste the URL at the top of this README.

**1. Deploy the backend**
1. Push this repo to GitHub (use an anonymous repo name, as the assignment asks).
2. In Vercel: *Add New → Project*, import the repo, set **Root Directory = `backend`**. Framework preset: *Other* / FastAPI (auto-detected from `index.py` + `requirements.txt`).
3. Deploy, then open `https://<backend>.vercel.app/api/health` — expect `{"status":"ok",...}`.
4. Open `https://<backend>.vercel.app/api/metrics` once to confirm it can reach Elexon and finishes within the function time limit. If the first call times out on your plan, raise the function's maximum duration in the Vercel project settings. (Requests to Elexon already run in parallel, so this should normally be a few seconds.)

**2. Deploy the frontend**
1. *Add New → Project*, same repo, **Root Directory = `frontend`**, framework preset *Vite*.
2. Add environment variable `VITE_API_BASE_URL = https://<backend>.vercel.app`.
3. Deploy.

**3. Allow the frontend to call the backend (CORS)**
In the backend project add `CORS_ORIGINS = https://<frontend>.vercel.app` and redeploy the backend.

**Notes.** Vercel functions are stateless: the in-memory cache lives per warm instance, so a cold start reloads Elexon data (a few seconds). That is acceptable for this scope; see *Future improvements*.

**Alternative (Heroku, backend):** from `backend/`, `heroku create`, `git subtree push --prefix backend heroku main` (the included `Procfile` starts uvicorn). Host the static frontend separately and point `VITE_API_BASE_URL` at the Heroku URL.

## Edge cases handled

| Case | Behaviour |
|---|---|
| Elexon down / timing out | Retries with backoff; then `502` with a friendly message; the UI shows an error with **Retry**. Failed loads are not cached. |
| Empty response | Honest empty result, warning shown, UI empty state. |
| Missing actual / missing forecast | Excluded from errors, **counted and displayed** in the data-quality panel. |
| Duplicate rows (incl. chunk-boundary overlap) | Collapsed and counted. |
| Multiple forecasts per `startTime` | The decision-time rule picks one. |
| Forecast published after the cutoff | Never used; counted. |
| Timezones / clock changes | UTC internally, UK local for days and display; 23/25-hour days counted correctly. |
| Zero / near-zero actual | MAE/RMSE/bias unaffected; excluded from MAPE with a visible count. |
| Malformed rows / unexpected JSON | Bad rows skipped and counted; wrong overall shape → `502`. |
| Invalid dates / outside January scope | `422` with an explanation; the date picker prevents them. |
| Partial month | Coverage % and warnings shown; recent actuals are often not yet published. |

## AI assistance

AI tools were used in building this project, as the assignment requires me to disclose. **Claude (Anthropic's AI assistant, via Claude Code)** was used to help with: project scaffolding, the FastAPI backend and data-processing code, the React/TypeScript frontend, the unit and API tests, Docker configuration, and drafting this README. The design decisions (forecast-selection rule, assumptions, metric choices) were discussed and documented here so they can be explained and challenged in review.

> `TODO (author): confirm this paragraph reflects how you actually worked and adjust it if needed — e.g. what you reviewed, changed or wrote yourself.`

## Limitations

- **Not verified against the live Elexon API in the build environment** (outbound access to Elexon was blocked). The live probe and time-grid verification (see [Time grids](#time-grids-live-evidence-vs-assumptions)) were run by the author on their own machine; re-run `python backend/scripts/probe_elexon.py` to reproduce them. They live in one place (`backend/app/services/elexon_client.py`) if anything needs adjusting. UI screenshots/behaviour were checked against a local *synthetic* stand-in for Elexon, never shipped and never used for real figures.
- The decision cutoff is an assumption (see above), and results depend on it.
- Docker images and the Vercel deployment were written but **not built/deployed in the sandbox** (no Docker daemon / no Vercel access). Python and frontend builds, type-checks and all tests were run.
- The `:30` FUELHH actuals are not used in accuracy metrics because no forecast exists for them.
- National totals only (no regional or offshore/onshore split), wind only, one month.
- The cache is in memory per process (cold start on serverless reloads the data).
- MAPE's 50 MW floor is a judgement call.

## Future improvements

- Evaluate accuracy **by lead time** (how much does the forecast improve as delivery approaches?) and by time of day / wind regime.
- Let users change the cutoff in the UI to see how sensitive the accuracy is to it ("what if we decided at 11:00?").
- Prediction intervals / quantified risk: translate historical error into a MW buffer for procurement.
- Add solar and demand; regional breakdown.
- Persistent cache (Redis / database) and scheduled refresh; CI pipeline; end-to-end browser tests.
- Optional: use the exact day-ahead gate-closure time from an authoritative source.

---

*Data: Elexon BMRS (FUELHH, WINDFOR), used under the BMRS Data Licence.*
