# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DealHawk is a Chrome extension + Python backend that scores vehicle deals on dealer websites. It detects aged inventory, calculates true dealer cost, and generates negotiation targets. Supports CarGurus, AutoTrader, Cars.com, and Edmunds. Has user accounts with JWT auth, saved vehicles, deal alerts, and Stripe subscription billing (Free + Pro tiers).

## Commands

```bash
# Setup
python -m venv venv && source venv/Scripts/activate  # Windows Git Bash
pip install -r backend/requirements.txt

# Run backend (localhost:8000, Swagger at /docs)
python -m backend.main

# Run all tests (140 tests; ignore test_vin_decoder if pytest_asyncio not installed)
pytest backend/tests/ --ignore=backend/tests/test_vin_decoder.py -v

# Run a single test file or test
pytest backend/tests/test_deal_scorer.py -v
pytest backend/tests/test_deal_scorer.py::TestDealScorer::test_ram_2500_aged_inventory -v

# Database migrations (Alembic)
alembic upgrade head          # Apply all migrations
alembic current               # Show current revision
alembic revision -m "desc"    # Create new migration

# Seed database with invoice prices and incentives
python -m backend.seed_data

# Create a dealer API key (for Dealer tier endpoints)
python -m backend.create_dealer_key --name "Dealer Name" --email "dealer@example.com"

# Load extension: Chrome → chrome://extensions → Developer mode → Load unpacked → select extension/
```

## Architecture

**Two independent components communicating over HTTP:**

```
Chrome Extension (Manifest V3)  →  Python Backend (FastAPI)
  4 content scripts (DOM scraping)     services (scoring, VIN, pricing, auth, stripe, market, tax)
  service worker (message router)      SQLite database (10 tables)
  popup + side panel (UI)              JWT auth + Stripe billing + Dealer API key auth
                                       Alembic migrations (4 revisions)
```

### Backend (`backend/`)

Layered: **API → Services → Database/Config**

- **API**: Eight route files — six under `/api/v1/`: `routes.py` (scoring, VIN, pricing, incentives, negotiation, Section 179 calculator), `auth_routes.py` (register, login, refresh, me), `saved_routes.py` (CRUD saved vehicles — Pro only), `alert_routes.py` (CRUD deal alerts — Pro only), `market_routes.py` (market trends + stats — free tier), `dealer_routes.py` (bulk scoring, market intel, inventory analysis — API key auth). Two at root: `subscription_routes.py` (checkout, portal, status, success/cancel pages), `webhook_routes.py` (Stripe webhook). Auth dependencies in `auth.py` provide `get_current_user_required`, `get_current_user_optional`, and `get_pro_user_required`. Dealer auth in `dealer_auth.py` provides `get_dealership_required` (X-API-Key header + rate limiting).
- **Services** (`services/`): Stateless functions. `deal_scorer.py` is the core — 5-factor weighted scoring. `auth_service.py` handles bcrypt hashing, JWT creation/verification, user registration. `stripe_service.py` handles Stripe customer creation, checkout sessions, portal sessions, and webhook event processing. `alert_service.py` matches listings against user alerts. `vin_decoder.py` calls NHTSA. `pricing_service.py` checks DB cache, falls back to ratio estimates. `negotiation_service.py` generates offers and talking points. `marketcheck_service.py` provides market trends/stats with DB caching (stub data or live MarketCheck API). `section179_service.py` calculates tax deductions for business vehicles.
- **Database** (`database/`): SQLAlchemy 2.0 mapped classes. SQLite for dev (Postgres ready via `DATABASE_URL`). Ten tables: `users` (with subscription fields), `vehicles` (VIN-keyed), `listing_sightings`, `invoice_price_cache`, `incentive_programs`, `saved_vehicles` (FK → users), `deal_alerts` (FK → users), `processed_webhook_events` (Stripe idempotency), `market_data_cache` (cached MarketCheck responses with TTL), `dealerships` (API tier accounts with rate limiting). Alembic manages migrations (`alembic/versions/`).
- **Config** (`config/`): `settings.py` uses pydantic-settings with `.env`. Includes JWT settings, Stripe keys, MarketCheck API key, dealer API key salt, and `environment` (development/production). `validate_production()` blocks startup if JWT secret, Stripe keys, or dealer salt are default in production. `holdback_rates.py`, `invoice_ranges.py`, and `section179_data.py` are static domain data.

### Extension (`extension/`)

- **Service worker** (`background/service-worker.js`): Central message router. All API calls go through `api-client.js` (avoids CORS). Caches responses in `chrome.storage.local` with 1-hour TTL.
- **API client** (`background/api-client.js`): HTTP methods with JWT token management. Stores tokens in `chrome.storage.local`. Auto-injects `Authorization: Bearer` header. Auto-refreshes on 401 with `_refreshInProgress` flag to prevent infinite retry loops.
- **Content scripts** (`content/`): Four site-specific scripts (cargurus.js, autotrader.js, carscom.js, edmunds.js) all follow the same IIFE pattern — `PROCESSED_ATTR` dedup, initial `setTimeout(scanPage)`, `MutationObserver` with debounce, `scanSearchResults()`/`scanDetailPage()` routing by URL, multi-selector fallbacks.
- **Overlay** (`content/overlay.js`): Injects score badges (0-100, color-coded) onto listing cards. Accepts optional `positionOverride` parameter for per-site positioning.
- **Side panel** (`sidepanel/`): Five tabs — Analysis (score gauge, price breakdown, offers, market context, talking points), Calculator (manual MSRP→cost→offers), Tax (Section 179 deduction calculator — free tier), Saved (Pro-gated, vehicle list with delete), Alerts (Pro-gated, CRUD alert criteria). Free users see "Pro subscription required" with inline upgrade button. Components in `sidepanel/components/`: `score-gauge.js`, `price-breakdown.js`, `offer-targets.js`, `tax-calculator.js`, `market-context.js`.
- **Popup** (`popup/`): Backend status, VIN lookup, login/register with auth tab switching, subscription tier badge (Free/Pro), upgrade button (opens Stripe checkout), manage subscription button (opens Stripe portal).

### Message Flow

Content script scrapes DOM → `chrome.runtime.sendMessage({action: 'SCORE_LISTING', data})` → service worker routes to `api-client.js` → `fetch('http://localhost:8000/api/v1/score')` → FastAPI → `deal_scorer.score_deal()` → response flows back → badge injected on listing card.

### Auth Flow

Popup login → `AUTH_LOGIN` action → service worker → `apiLogin()` in api-client.js → `POST /api/v1/auth/login` → JWT access + refresh tokens stored in `chrome.storage.local` → all subsequent requests include `Authorization: Bearer <token>` → on 401, auto-refresh once then retry.

### Subscription Flow

Popup "Upgrade to Pro" button → `CREATE_CHECKOUT` action → service worker → `createCheckout()` → `POST /subscription/checkout` (authenticated) → backend creates Stripe Checkout Session → returns URL → extension opens in new tab via `chrome.tabs.create()` → user completes payment on Stripe hosted page → Stripe sends `checkout.session.completed` webhook → `POST /webhooks/stripe` → `process_checkout_completed()` upgrades user to Pro → extension refreshes `/auth/me` to detect new tier.

## Deal Scoring Algorithm

Five weighted factors (0–100 total):

| Factor | Weight | What it measures |
|--------|--------|-----------------|
| Price vs True Dealer Cost | 35% | Asking price relative to invoice minus holdback minus dealer cash |
| Days on Lot | 25% | Longer = more dealer pain (floor plan costs ~$7.90/day) |
| Available Incentives | 20% | Rebates as percentage of MSRP |
| Market Supply | 12% | Model's days supply vs 76-day industry average |
| Timing/Seasonal | 8% | Month-end, quarter-end, year-end bonuses |

Market data (days supply by model) is hardcoded in `deal_scorer.MODEL_DAYS_SUPPLY` from February 2026 research in `TRUCK_BUYING_GUIDE.md`.

## Key Conventions

- Python imports use full paths from project root: `from backend.services.deal_scorer import score_deal`
- Extension JS uses ES module imports in service worker, IIFEs in content scripts (no module support in content script context)
- Chrome extension message actions use SCREAMING_SNAKE_CASE: `SCORE_LISTING`, `AUTH_LOGIN`, `SAVE_VEHICLE`
- Private Python functions prefixed with underscore: `_score_price()`, `_calculate_offers()`
- Auth-required endpoints use `Depends(get_current_user_required)`; Pro-only endpoints (saved, alerts) use `Depends(get_pro_user_required)`; free-tier endpoints use no auth or `get_current_user_optional`
- Invoice/holdback data: Ram/Ford holdback = 3% of MSRP; GM = 3% of invoice. See `holdback_rates.py`.
- `invoice_ranges.py` lookup tries `"{make} {model}"` then just `"{model}"` to handle cases like "Ram Ram 2500"

## Testing Patterns

- Tests use in-memory SQLite with `patch("backend.database.db.SessionLocal", TestSession)` to isolate the DB
- Each test fixture creates a fresh engine with `StaticPool`, runs `Base.metadata.create_all`
- Auth tests register a user via fixture, then use the returned tokens for authenticated requests
- Saved/alerts tests register a user then upgrade to Pro tier in DB before making requests
- Stripe calls in tests are mocked with `unittest.mock.patch` — no real Stripe keys needed
- Password hashing uses bcrypt directly (not passlib — incompatible with bcrypt >= 4.1)
- Custom `DuplicateEmailError` exception (not ValueError) for registration conflicts
- Dealer API tests create a `Dealership` directly in DB with a known API key hash, then pass `X-API-Key` header

## Security Conventions

These patterns were established during security hardening and must be maintained:

- **No `innerHTML` in extension code.** All DOM rendering uses `document.createElement()` + `textContent`. This prevents XSS from scraped page data or API responses. Grep for `innerHTML` — there should be zero matches in `extension/`.
- **VIN validation is character-strict.** `vin_decoder.py` enforces `[A-HJ-NPR-Z0-9]{17}` via regex (VINs exclude I, O, Q). This prevents path traversal in the NHTSA URL.
- **API input bounds.** Pydantic `Field()` constraints on all numeric request fields (prices capped at 500K, years 1980–2030, days 0–3650). Prevents division-by-zero and absurd calculations.
- **CORS is locked to real extension IDs.** The regex `^chrome-extension://[a-z]{32}$` matches only valid Chrome extension origin format. Credentials are disabled. Only GET/POST/PATCH/DELETE allowed.
- **No internal error details in responses.** Backend catches exceptions and returns generic messages (e.g. `"upstream service unavailable"`), not Python tracebacks.
- **URL parameters are encoded.** `api-client.js` uses `encodeURIComponent()` on all path and query parameters.
- **JWT secret guard.** `settings.validate_production()` raises on startup if the default dev secret is used in production.
- **Timing attack mitigation.** `authenticate_user()` runs a dummy bcrypt check on non-existent users to prevent email enumeration via response time.
- **Passwords hashed with bcrypt directly.** Not passlib (broken with bcrypt >= 4.1). `DuplicateEmailError` is a custom exception, not ValueError, to prevent register endpoint from masking hash errors as "email already exists".
- **Dealer API key comparison is constant-time.** `dealer_auth.py` fetches all active dealers and uses `hmac.compare_digest()` against each hash — prevents timing-based API key enumeration.
- **Rate limit counters use atomic SQL UPDATE.** `Dealership.requests_today + 1` is evaluated at DB level (not Python) to prevent race conditions under concurrent load.
- **External service calls wrapped in try-except.** `market_routes.py` and `dealer_routes.py` catch exceptions from MarketCheck/DB and return generic 502 with `logger.exception()` server-side only.
- **Path parameters validated.** All Phase 4+ endpoints use `Path(..., min_length=1, max_length=N)` to reject malformed input at the API layer.
- **Frontend error messages are generic.** Catch blocks in sidepanel.js and popup.js display hardcoded strings, never `err.message` (which may contain backend response text).

## Seed Data

`backend/seed_data.py` loads 32 invoice price records and 23 incentive programs from February 2026 market research. Data covers F-150, F-250, Ram 1500/2500/3500, Silverado 1500/2500HD, Sierra 1500/2500HD. Re-run after schema changes: `python -m backend.seed_data`.

## Phase Status

- **Phase 1 (MVP)**: Complete — CarGurus content script, backend scoring/VIN/pricing/negotiation, side panel UI
- **Phase 2**: Complete — AutoTrader/Cars.com/Edmunds content scripts, user auth (JWT), saved vehicles, deal alerts, privacy policy, deployment prep
- **Phase 3**: Complete — Stripe subscription billing (Free + Pro tiers), Alembic migrations, tier enforcement (saved/alerts = Pro only), subscription UI in popup + side panel, Chrome Web Store prep (CSP, store listing, privacy policy update), security-audited (0 findings). Celery/Redis deferred.
- **Phase 4**: Complete — MarketCheck API integration (stub-first with clean swap interface), Section 179 tax calculator (free tier, IRC §280F luxury auto limits, OBBBA 100% bonus depreciation), Dealership API tier (X-API-Key auth, bulk scoring, market intel, inventory analysis, rate limiting), market context in Analysis tab, 140 tests passing, 3 audit rounds (0 findings). `create_dealer_key.py` CLI for dealer onboarding.
- **Phase 5**: Celery background tasks, PostgreSQL migration, live MarketCheck API integration, dealer dashboard
