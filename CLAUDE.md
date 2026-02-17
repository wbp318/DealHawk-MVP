# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DealHawk is a Chrome extension + Python backend that scores vehicle deals on dealer websites. It detects aged inventory, calculates true dealer cost, and generates negotiation targets. Currently supports CarGurus only (MVP); AutoTrader, Cars.com, Edmunds planned for Phase 2.

## Commands

```bash
# Setup
python -m venv venv && source venv/Scripts/activate  # Windows Git Bash
pip install -r backend/requirements.txt

# Run backend (localhost:8000, Swagger at /docs)
python -m backend.main

# Run all tests
pytest backend/tests/

# Run a single test file or test
pytest backend/tests/test_deal_scorer.py -v
pytest backend/tests/test_deal_scorer.py::TestDealScorer::test_ram_2500_aged_inventory -v

# Seed database with invoice prices and incentives
python -m backend.seed_data

# Load extension: Chrome → chrome://extensions → Developer mode → Load unpacked → select extension/
```

## Architecture

**Two independent components communicating over HTTP:**

```
Chrome Extension (Manifest V3)  →  Python Backend (FastAPI)
  content scripts (DOM scraping)       services (scoring, VIN, pricing)
  service worker (message router)      SQLite database
  popup + side panel (UI)              NHTSA API (VIN decode)
```

### Backend (`backend/`)

Layered: **API → Services → Database/Config**

- **API** (`api/routes.py`): Six endpoints under `/api/v1/`. Pydantic request models with `Field()` validation constraints (bounds on prices, years, string lengths). DB sessions via FastAPI `Depends(get_db)`.
- **Services** (`services/`): Stateless functions. `deal_scorer.py` is the core — 5-factor weighted scoring. `vin_decoder.py` calls NHTSA (free, no key) with VIN character validation. `pricing_service.py` checks DB cache first, falls back to ratio estimates. `negotiation_service.py` generates dollar-amount offers and scripted talking points.
- **Database** (`database/`): SQLAlchemy 2.0 mapped classes. SQLite for MVP (Postgres planned). Four tables: `vehicles` (VIN-keyed), `listing_sightings`, `invoice_price_cache`, `incentive_programs`.
- **Config** (`config/`): `settings.py` uses pydantic-settings with `.env`. Debug defaults to `False` (opt-in via `.env`). `holdback_rates.py` and `invoice_ranges.py` are static domain data (holdback percentages, invoice-to-MSRP ratios by make/model/trim tier).

### Extension (`extension/`)

- **Service worker** (`background/service-worker.js`): Central message router. All API calls go through here (avoids CORS). Caches responses in `chrome.storage.local` with 1-hour TTL.
- **Content script** (`content/cargurus.js`): Scrapes CarGurus listing cards and detail pages. Uses MutationObserver for React-rendered content. Sends extracted data to service worker for scoring.
- **Overlay** (`content/overlay.js`): Injects score badges (0-100, color-coded green/yellow/red) onto listing cards. Click opens side panel.
- **Side panel** (`sidepanel/`): Three tabs — Analysis (score gauge, price breakdown, offers, talking points), Calculator (manual MSRP→cost→offers), Saved (placeholder).
- **Popup** (`popup/`): Quick status display and VIN lookup input.

### Message Flow

Content script scrapes DOM → `chrome.runtime.sendMessage({action: 'SCORE_LISTING', data})` → service worker routes to `api-client.js` → `fetch('http://localhost:8000/api/v1/score')` → FastAPI → `deal_scorer.score_deal()` → response flows back → badge injected on listing card.

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
- Chrome extension message actions use SCREAMING_SNAKE_CASE: `SCORE_LISTING`, `DECODE_VIN`, `GET_NEGOTIATION`
- Private Python functions prefixed with underscore: `_score_price()`, `_calculate_offers()`
- Invoice/holdback data: Ram/Ford holdback = 3% of MSRP; GM = 3% of invoice. See `holdback_rates.py`.
- `invoice_ranges.py` lookup tries `"{make} {model}"` then just `"{model}"` to handle cases like "Ram Ram 2500"

## Security Conventions

These patterns were established during security hardening and must be maintained:

- **No `innerHTML` in extension code.** All DOM rendering uses `document.createElement()` + `textContent`. This prevents XSS from scraped page data or API responses. Grep for `innerHTML` — there should be zero matches in `extension/`.
- **VIN validation is character-strict.** `vin_decoder.py` enforces `[A-HJ-NPR-Z0-9]{17}` via regex (VINs exclude I, O, Q). This prevents path traversal in the NHTSA URL.
- **API input bounds.** Pydantic `Field()` constraints on all numeric request fields (prices capped at 500K, years 1980–2030, days 0–3650). Prevents division-by-zero and absurd calculations.
- **CORS is locked to real extension IDs.** The regex `^chrome-extension://[a-z]{32}$` matches only valid Chrome extension origin format. Credentials are disabled. Only GET/POST allowed.
- **No internal error details in responses.** Backend catches exceptions and returns generic messages (e.g. `"upstream service unavailable"`), not Python tracebacks.
- **URL parameters are encoded.** `api-client.js` uses `encodeURIComponent()` on all path and query parameters.

## Seed Data

`backend/seed_data.py` loads 32 invoice price records and 23 incentive programs from February 2026 market research. Data covers F-150, F-250, Ram 1500/2500/3500, Silverado 1500/2500HD, Sierra 1500/2500HD. Re-run after schema changes: `python -m backend.seed_data`.

## Phase Status

- **Phase 1 (MVP)**: Complete — CarGurus content script, backend scoring/VIN/pricing/negotiation, side panel UI
- **Phase 2**: AutoTrader/Cars.com/Edmunds content scripts, user auth (JWT), saved vehicles, deal alerts
- **Phase 3**: Stripe subscriptions, Chrome Web Store, PostgreSQL migration, Celery background tasks
- **Phase 4**: Dealership API tier, MarketCheck API, market trends, Section 179 calculator
