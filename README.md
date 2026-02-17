# DealHawk

Chrome extension that scores vehicle deals, calculates true dealer cost, and generates negotiation targets. Built for the February 2026 truck market where Ram has 300+ days supply, Ford F-Series is at 100+, and ~700K leftover 2025 models are sitting on lots.

## What It Does

Browse CarGurus, AutoTrader, Cars.com, or Edmunds and DealHawk automatically:

- **Scores every listing 0-100** using a 5-factor algorithm (price vs dealer cost, days on lot, rebates, market supply, timing)
- **Calculates true dealer cost** -- invoice minus holdback minus dealer cash, not the inflated number dealers quote
- **Generates three offer targets** -- aggressive, reasonable, and likely settlement prices based on how long the truck has been sitting
- **Produces negotiation scripts** -- specific dollar amounts and talking points referencing floor plan costs, curtailment penalties, and competing quotes
- **Shows market context** -- days supply vs industry average, supply level, price trends, active incentives
- **Section 179 tax calculator** -- estimate first-year deduction for business vehicles (GVWR-aware, pickup truck exemptions, IRC section 280F limits)

## Tiers

| Feature | Free | Pro ($9.99/mo) | Dealer (API key) |
|---------|------|-----------------|------------------|
| Deal scoring (0-100) | Y | Y | Bulk (50/request) |
| True dealer cost | Y | Y | Y |
| Offer targets + scripts | Y | Y | Y |
| VIN decoder | Y | Y | Y |
| Section 179 calculator | Y | Y | -- |
| Market trends | Y | Y | Higher rate limits |
| Save vehicles | -- | Y | -- |
| Deal alerts | -- | Y | -- |
| Inventory analysis | -- | -- | Y (100/request) |
| Incentives lookup | -- | -- | Y |

## Architecture

```
Chrome Extension (Manifest V3)  -->  Python Backend (FastAPI + SQLite)
  4 content scripts (DOM scraping)      9 services, 8 route files
  service worker (message router)       10 tables (SQLAlchemy 2.0 + Alembic)
  popup + side panel (5 tabs)           JWT auth + Stripe billing + Dealer API keys
```

**Extension** injects score badges onto listing cards on CarGurus, AutoTrader, Cars.com, and Edmunds. Click a badge to open a side panel with full deal analysis, price breakdown, market context, and negotiation brief. Side panel has five tabs: Analysis, Calculator, Tax, Saved, and Alerts. Popup provides VIN lookup, login/register, and subscription management.

**Backend** scores deals, decodes VINs (NHTSA API), looks up invoice pricing, calculates Section 179 deductions, provides market trends, and generates negotiation intelligence. Seeded with February 2026 invoice data and incentives for F-150, F-250, Ram 1500/2500/3500, Silverado, and Sierra. Dealer API tier provides bulk scoring, inventory analysis, and incentives lookup via API key auth.

## Quick Start

```bash
# Backend
python -m venv venv && source venv/Scripts/activate  # Windows Git Bash
pip install -r backend/requirements.txt
alembic upgrade head
python -m backend.seed_data
python -m backend.main          # localhost:8000, Swagger at /docs

# Extension
# Chrome -> chrome://extensions -> Developer mode -> Load unpacked -> select extension/
```

Browse to any supported site and search for trucks. Score badges appear on listings. Click one to open the analysis panel.

## API

Backend runs at `localhost:8000` with Swagger docs at `/docs`.

### Consumer Endpoints (no auth required)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/vin/{vin}` | GET | Decode VIN via NHTSA |
| `/api/v1/score` | POST | Score a listing (0-100 + offer targets) |
| `/api/v1/negotiate` | POST | Full negotiation brief with talking points |
| `/api/v1/pricing/{year}/{make}/{model}` | GET | Invoice, holdback, true dealer cost |
| `/api/v1/incentives/{make}` | GET | Current rebates and financing offers |
| `/api/v1/section-179/calculate` | POST | Section 179 tax deduction estimate |
| `/api/v1/market/trends/{make}/{model}` | GET | Days supply, price trend, incentive summary |
| `/api/v1/market/stats/{make}/{model}` | GET | Price ranges, median days on lot |

### Auth Endpoints (JWT)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/register` | POST | Create account |
| `/api/v1/auth/login` | POST | Get access + refresh tokens |
| `/api/v1/auth/refresh` | POST | Refresh access token |
| `/api/v1/auth/me` | GET | Current user + subscription info |

### Pro Endpoints (JWT + Pro subscription)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/saved` | GET/POST | List/save vehicles |
| `/api/v1/saved/{id}` | GET/PATCH/DELETE | Get/update/delete saved vehicle |
| `/api/v1/alerts` | GET/POST | List/create deal alerts |
| `/api/v1/alerts/{id}` | PATCH/DELETE | Update/delete alert |

### Dealer Endpoints (X-API-Key header)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/dealer/score/bulk` | POST | Score up to 50 vehicles per request |
| `/api/v1/dealer/market/{make}/{model}` | GET | Market trends (higher rate limits) |
| `/api/v1/dealer/incentives/{make}` | GET | Incentives with optional model filter |
| `/api/v1/dealer/inventory/analysis` | POST | Aged inventory analysis (up to 100 vehicles) |

```bash
# Create a dealer API key
python -m backend.create_dealer_key --name "Dealer Name" --email "dealer@example.com"
```

### Subscription Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/subscription/checkout` | POST | Create Stripe checkout session |
| `/subscription/portal` | POST | Open Stripe billing portal |
| `/subscription/status` | GET | Current subscription status |
| `/webhooks/stripe` | POST | Stripe webhook receiver |

## Scoring Example

```
POST /api/v1/score
{
  "asking_price": 55000,
  "msrp": 65000,
  "make": "Ram",
  "model": "Ram 2500",
  "year": 2025,
  "days_on_lot": 200,
  "rebates_available": 10000
}

-> Score: 89/100 (Grade A)
-> True Dealer Cost: $56,550
-> Aggressive Offer: $49,400
-> Reasonable Offer: $53,300
-> Carrying Costs: $1,580
```

## Tests

```bash
pytest backend/tests/ --ignore=backend/tests/test_vin_decoder.py -v   # 140 tests
pytest backend/tests/test_deal_scorer.py -v                           # single file
```

## Configuration

Copy `.env.example` to `.env`. Key settings:

| Variable | Required | Purpose |
|----------|----------|---------|
| `JWT_SECRET_KEY` | Production | Auth token signing (change from default!) |
| `STRIPE_SECRET_KEY` | Subscriptions | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | Subscriptions | Stripe webhook verification |
| `STRIPE_PRO_PRICE_ID` | Subscriptions | Stripe price ID for Pro tier |
| `MARKETCHECK_API_KEY` | Optional | Live market data (uses stub data if unset) |
| `DEALER_API_KEY_SALT` | Production | Salt for dealer API key hashing (change from default!) |

## Roadmap

- **Phase 1 (MVP)** -- Complete. CarGurus + backend scoring + side panel UI.
- **Phase 2** -- Complete. AutoTrader, Cars.com, Edmunds. User accounts (JWT), saved vehicles, deal alerts.
- **Phase 3** -- Complete. Stripe subscriptions (Free/Pro tiers), Alembic migrations, tier enforcement, Chrome Web Store prep, security audit (0 findings).
- **Phase 4** -- Complete. MarketCheck API (stub-first), Section 179 calculator, Dealership API tier (bulk scoring, inventory analysis, rate limiting), market trends in Analysis tab, 140 tests, 3 audit rounds (0 findings).
- **Phase 5** -- Celery background tasks, PostgreSQL migration, live MarketCheck API, dealer dashboard.

## License

Proprietary. See [LICENSE](LICENSE).
