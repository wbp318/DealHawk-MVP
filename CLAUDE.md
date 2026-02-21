# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DealHawk is a **public web app** + Chrome extension + Python backend that scores vehicle deals. The web app (`/`, `/tools/*`, `/account/*`) is the primary product — server-rendered Jinja2 + HTMX, no build step. The Chrome extension is a power-user add-on that overlays scores on CarGurus, AutoTrader, Cars.com, and Edmunds. Built for the February 2026 truck market.

## Commands

```bash
# Setup
python -m venv venv && source venv/Scripts/activate  # Windows Git Bash
pip install -r backend/requirements.txt

# Run backend (localhost:8000, Swagger at /docs)
python -m backend.main

# Run all tests (265 tests across 19 files)
pytest backend/tests/ --ignore=backend/tests/test_vin_decoder.py -v

# Run a single test file or test
pytest backend/tests/test_deal_scorer.py -v
pytest backend/tests/test_deal_scorer.py::TestDealScorer::test_ram_2500_aged_inventory -v

# Database migrations
alembic upgrade head          # Apply all
alembic revision -m "desc"    # Create new

# Seed database with invoice prices and incentives
python -m backend.seed_data

# Create a dealer API key
python -m backend.create_dealer_key --name "Dealer Name" --email "dealer@example.com"
python -m backend.create_dealer_key --name "Dashboard Dealer" --email "d@test.com" --password "pass123"

# Docker (production) — 5 services: app, db, redis, celery-worker, celery-beat
docker compose up --build

# Celery (local dev with Redis running)
celery -A backend.celery_app worker --loglevel=info
celery -A backend.celery_app beat --loglevel=info
```

## Environment Configuration

Copy `.env.example` to `.env` — it is the source of truth for all config variables and their defaults.

Three environment modes controlled by `ENVIRONMENT` env var:
- **development** (default): SQLite, `init_db()` auto-creates tables, Swagger at `/docs`, no secret validation
- **staging**: PostgreSQL, Alembic in Dockerfile, Swagger at `/docs`, no strict secret validation
- **production**: PostgreSQL, Alembic, no Swagger, `validate_production()` blocks startup if JWT secret, Stripe keys, dealer salt, or Redis URL are default/missing

The extension's `API_HOST` in `extension/background/api-client.js` defaults to the production Render URL. For local dev, uncomment the `localhost:8000` line.

## Deployment (Render)

Deployed via `render.yaml` blueprint (free-tier web service + free PostgreSQL). Redis/Celery are skipped — code falls back to sync processing when `REDIS_URL` is empty.

- **Production URL**: `https://dealhawk-api.onrender.com`
- **Deploy**: Push to `main` → Render auto-builds from Dockerfile → `alembic upgrade head` → uvicorn
- **Seed after deploy**: Render Shell tab → `python -m backend.seed_data`
- **Free tier**: Server sleeps after 15 min idle, ~30s cold start on first request
- **BASE_URL**: Stripe redirects use `settings.base_url` — defaults to `http://localhost:8000`, must be set to `https://dealhawk-api.onrender.com` in production for checkout/portal return URLs to work

## Architecture

**Three components sharing a single FastAPI backend:**

```
Public Web App (Jinja2 + HTMX)    Chrome Extension (Manifest V3)    Python Backend (FastAPI)
  Landing page + 4 free tools        4 content scripts (DOM scraping)    11 route files, 10 services
  Consumer auth (session cookies)    service worker (message router)     10 tables (SQLAlchemy 2.0 + Alembic)
  Account: saved, alerts, billing    popup + side panel (5 tabs)         3 auth systems (see below)
  SEO (robots.txt, sitemap.xml)                                         Celery + Redis (background tasks)
```

### Three Auth Systems

| System | Cookie/Token | Used By | Salt/Secret | Max Age |
|--------|-------------|---------|-------------|---------|
| JWT (access + refresh) | `Authorization: Bearer` header | Chrome extension, API | `jwt_secret_key` | 30min / 7d |
| `dh_web_session` cookie | Signed cookie (itsdangerous) | Web app consumers | `jwt_secret_key + "-web"` | 7 days |
| `dh_dealer_session` cookie | Signed cookie (itsdangerous) | Dealer dashboard | `jwt_secret_key` | 24 hours |

All three call the same `auth_service.py` (bcrypt, `authenticate_user()`, `register_user()`). Extension API key auth for dealers is a fourth mechanism via `X-API-Key` header (constant-time hash comparison in `dealer_auth.py`).

### Router Registration Order (app.py)

Order matters — FastAPI matches first registered route. `web_router` is **last** to avoid catching `/api/v1/*`, `/dashboard/*`, `/subscription/*`, or `/webhooks/*` routes.

```
/api/v1/*       → routes, auth_routes, saved_routes, alert_routes, market_routes, dealer_routes
/dashboard/*    → dashboard_router (dealer dashboard)
/subscription/* → subscription_router
/webhooks/*     → webhook_router
/*              → web_router (catch-all: /, /tools/*, /login, /account/*, /robots.txt, /sitemap.xml)
```

### Backend (`backend/`)

Layered: **API → Services → Database/Config**

- **API** (`api/`): 11 route files. Core pattern: FastAPI router with Pydantic request/response models. Web app and dealer dashboard use Jinja2 + HTMX (form POST → partial HTML swap). Auth dependencies: `get_current_user_required`, `get_current_user_optional`, `get_pro_user_required` (in `auth.py`), `get_dealership_required` (in `dealer_auth.py`).
- **Services** (`services/`): Stateless functions called by routes. Core: `deal_scorer.score_deal()` (5-factor weighted scoring), `vin_decoder.decode_vin()` (async, NHTSA API), `pricing_service.get_pricing()` (DB cache → ratio fallback), `section179_service.calculate_section_179()`, `marketcheck_service.get_market_trends/stats()` (retry + circuit breaker → stub fallback), `auth_service.py` (bcrypt, JWT), `stripe_service.py` (checkout, portal, webhooks).
- **Tasks** (`tasks/`): Celery background tasks. Autodiscovered via `app.autodiscover_tasks(["backend.tasks"])` in `celery_app.py`. Tasks create their own `SessionLocal()` and close in `finally`. Beat schedule: market cache refresh every 6 hours.
- **Database** (`database/`): SQLAlchemy 2.0 mapped classes in `models.py`. 10 tables. SQLite for dev, PostgreSQL for production. Alembic migrations in `alembic/versions/`. `render_as_batch` conditional (SQLite only).
- **Config** (`config/`): `settings.py` (pydantic-settings, `.env`). Static domain data: `holdback_rates.py`, `invoice_ranges.py`, `section179_data.py`.
- **Templates** (`templates/`): Three directories — `web/` (consumer app), `dealer/` (dashboard), `email/` (notifications). All use Jinja2 auto-escaping.
- **Static** (`static/`): `web.css` (consumer app), `dashboard.css` (dealer dashboard).

### Extension (`extension/`)

- **Service worker** (`background/service-worker.js`): Message router. All API calls go through `api-client.js`. Caches in `chrome.storage.local` with 1-hour TTL.
- **Content scripts** (`content/`): Four site-specific IIFEs (cargurus.js, autotrader.js, carscom.js, edmunds.js). Pattern: `PROCESSED_ATTR` dedup → `setTimeout(scanPage)` → `MutationObserver` with debounce → `scanSearchResults()`/`scanDetailPage()` by URL.
- **Side panel** (`sidepanel/`): Five tabs — Analysis, Calculator, Tax, Saved (Pro), Alerts (Pro).
- **Popup** (`popup/`): Status, VIN lookup, login/register, subscription management.

### Key Flows

**Web app tool**: User visits `/tools/score` → HTMX `hx-post` → `web_app.py` calls `score_deal()` directly (no HTTP) → returns `_score_results.html` partial → swaps into `#results` div. VIN route is `async def` (only async route — `decode_vin()` is async).

**Extension scoring**: Content script scrapes DOM → `chrome.runtime.sendMessage({action: 'SCORE_LISTING'})` → service worker → `api-client.js` → `POST /api/v1/score` → `deal_scorer.score_deal()` → badge injected.

**Stripe checkout**: User clicks Upgrade → `create_checkout_session(return_path="/account/subscription?success=true")` → Stripe hosted page → webhook → Celery (or sync fallback) → user upgraded to Pro.

## Deal Scoring Algorithm

Five weighted factors (0–100 total):

| Factor | Weight | What it measures |
|--------|--------|-----------------|
| Price vs True Dealer Cost | 35% | Asking price relative to invoice − holdback − dealer cash |
| Days on Lot | 25% | Longer = more dealer pain (floor plan costs ~$7.90/day) |
| Available Incentives | 20% | Rebates as percentage of MSRP |
| Market Supply | 12% | Model's days supply vs 76-day industry average |
| Timing/Seasonal | 8% | Month-end, quarter-end, year-end bonuses |

Days supply data hardcoded in `deal_scorer.MODEL_DAYS_SUPPLY` from Feb 2026 research.

## Key Conventions

- Python imports use full paths: `from backend.services.deal_scorer import score_deal`
- Extension JS: ES module imports in service worker, IIFEs in content scripts
- Chrome message actions: SCREAMING_SNAKE_CASE (`SCORE_LISTING`, `AUTH_LOGIN`)
- Private functions: underscore prefix (`_score_price()`, `_calculate_offers()`)
- Auth decorators: `Depends(get_current_user_required)` for auth, `Depends(get_pro_user_required)` for Pro-only
- Invoice lookup: `invoice_ranges.py` tries `"{make} {model}"` then `"{model}"` (handles "Ram Ram 2500")
- Holdback: Ram/Ford = 3% of MSRP; GM = 3% of invoice
- Webhook route dispatches to Celery when `settings.redis_url` is set, else sync fallback
- Web app tool routes call services directly (no HTTP round-trip to the API)
- Web app input validation uses manual helpers (mirrors Pydantic Field bounds) since HTML forms bypass Pydantic
- `stripe_service.create_checkout_session()` and `create_portal_session()` accept optional `return_path`/`cancel_path` for web app redirects

## Testing Patterns

- In-memory SQLite with `patch("backend.database.db.SessionLocal", TestSession)` per test
- Each fixture creates fresh engine with `StaticPool` + `Base.metadata.create_all`
- Mock patching targets where imported, not where defined: `@patch("backend.api.routes.decode_vin")` not `@patch("backend.services.vin_decoder.decode_vin")`
- Auth tests: register user via fixture, use returned tokens
- Pro tests: register + upgrade tier in DB before requests
- Stripe: mocked with `unittest.mock.patch`, no real keys needed
- Dealer API tests: create `Dealership` in DB with known hash, pass `X-API-Key`
- Web app tests: `_login()` helper returns cookies, `AsyncMock` for `decode_vin` via `with patch(...)` context manager (not decorator — fixture ordering issue)
- Dashboard tests: login via POST, capture session cookie
- Celery tasks: mock `SessionLocal` at task module level, no Redis needed
- MarketCheck tests: `reset_circuit_breaker()` fixture, mock `httpx.get`

## Security Conventions

These were established during security hardening and must be maintained:

- **No `innerHTML` in extension code.** All DOM uses `createElement()` + `textContent`. Zero matches for `innerHTML` in `extension/`.
- **VIN validation**: `[A-HJ-NPR-Z0-9]{17}` regex (excludes I, O, Q). Prevents path traversal.
- **API input bounds**: Pydantic `Field()` constraints (prices ≤500K, years 1980–2030, days ≤3650). Web app mirrors these in manual validation helpers.
- **CORS**: Regex `^chrome-extension://[a-z]{32}$` + localhost + Render domain. Credentials disabled.
- **No internal error details in responses.** Generic messages only; `logger.exception()` server-side.
- **JWT secret guard**: `validate_production()` raises on startup if default dev secret used in production.
- **Timing attack mitigation**: `authenticate_user()` runs dummy bcrypt on non-existent users. Dealer API key comparison uses `hmac.compare_digest()`.
- **Passwords**: bcrypt directly (not passlib — broken with bcrypt ≥ 4.1). `DuplicateEmailError` custom exception.
- **Rate limits**: Atomic SQL UPDATE (`Dealership.requests_today + 1` at DB level).
- **MarketCheck circuit breaker**: Opens after 5 failures, blocks 5 minutes, falls back to stubs.
- **Templates**: Jinja2 auto-escaping everywhere. No `|safe` on user data. No inline JS.
- **Session cookies**: Signed via `itsdangerous`, `httponly=True`, `samesite="lax"`. Web and dealer cookies use different names and salts.

## Seed Data

`backend/seed_data.py` loads 32 invoice prices + 23 incentive programs (Feb 2026 market data). Covers F-150, F-250, Ram 1500/2500/3500, Silverado 1500/2500HD, Sierra 1500/2500HD. Re-run after schema changes: `python -m backend.seed_data`.

## Cache TTLs

| Cache | TTL | Refresh |
|-------|-----|---------|
| Extension API responses (`chrome.storage.local`) | 1 hour | On next request |
| MarketCheck data (`market_data_cache` table) | 24 hours (configurable) | Celery beat every 6 hours |
| Invoice prices (`invoice_price_cache` table) | Permanent | Manual via `seed_data.py` |
