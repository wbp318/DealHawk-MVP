# DealHawk

Chrome extension that scores vehicle deals, calculates true dealer cost, and generates negotiation targets. Built for the February 2026 truck market where Ram has 300+ days supply, Ford F-Series is at 100+, and ~700K leftover 2025 models are sitting on lots.

## What It Does

Browse CarGurus and DealHawk automatically:

- **Scores every listing 0-100** using a 5-factor algorithm (price vs dealer cost, days on lot, rebates, market supply, timing)
- **Calculates true dealer cost** — invoice minus holdback minus dealer cash, not the inflated number dealers quote
- **Generates three offer targets** — aggressive, reasonable, and likely settlement prices based on how long the truck has been sitting
- **Produces negotiation scripts** — specific dollar amounts and talking points referencing floor plan costs, curtailment penalties, and competing quotes

## Architecture

```
Chrome Extension (Manifest V3)  →  Python Backend (FastAPI + SQLite)
```

**Extension** injects score badges onto CarGurus listing cards. Click a badge to open a side panel with full deal analysis, price breakdown, and negotiation brief. Popup provides quick VIN lookup.

**Backend** scores deals, decodes VINs (NHTSA API), looks up invoice pricing, and generates negotiation intelligence. Seeded with February 2026 invoice data and incentives for F-150, F-250, Ram 1500/2500/3500, Silverado, and Sierra.

## Quick Start

```bash
# Backend
python -m venv venv && source venv/Scripts/activate
pip install -r backend/requirements.txt
python -m backend.seed_data
python -m backend.main          # localhost:8000

# Extension
# Chrome → chrome://extensions → Developer mode → Load unpacked → select extension/
```

Browse to [cargurus.com](https://www.cargurus.com) and search for trucks. Score badges appear on listings. Click one to open the analysis panel.

## API

Backend runs at `localhost:8000` with Swagger docs at `/docs`.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/vin/{vin}` | GET | Decode VIN via NHTSA |
| `/api/v1/score` | POST | Score a listing (returns 0-100 + offer targets) |
| `/api/v1/negotiate` | POST | Full negotiation brief with talking points |
| `/api/v1/pricing/{year}/{make}/{model}` | GET | Invoice, holdback, true dealer cost |
| `/api/v1/incentives/{make}` | GET | Current rebates and financing offers |

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

→ Score: 89/100 (Grade A)
→ True Dealer Cost: $56,550
→ Aggressive Offer: $49,400
→ Reasonable Offer: $53,300
→ Carrying Costs: $1,580
```

## Tests

```bash
pytest backend/tests/ -v        # 29 tests: scoring, pricing, holdback, VIN decode
```

## Roadmap

- **Phase 1 (MVP)** — Complete. CarGurus + backend scoring + side panel UI.
- **Phase 2** — AutoTrader, Cars.com, Edmunds content scripts. User accounts, saved vehicles, deal alerts.
- **Phase 3** — Stripe subscriptions (Free / $9.99 Pro / $29.99 Dealership). Chrome Web Store. PostgreSQL.
- **Phase 4** — Dealership API tier, market trends, Section 179 calculator.

## License

Proprietary. See [LICENSE](LICENSE).
