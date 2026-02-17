# DealHawk — Chrome Web Store Listing Reference

## Title
DealHawk - Vehicle Deal Scorer

## Summary (132 char max)
Score vehicle deals 0-100. True dealer cost, negotiation targets, Section 179 tax calculator on CarGurus, AutoTrader & more.

## Full Description

DealHawk analyzes vehicle listings in real time and tells you exactly how good the deal is — before you ever talk to a dealer.

**How it works:**
Browse trucks and SUVs on CarGurus, AutoTrader, Cars.com, or Edmunds. DealHawk automatically scores each listing from 0-100 based on five factors: price vs true dealer cost, days on lot, available incentives, market supply, and timing.

**What you get (Free):**
- Deal scores on every listing (0-100 with letter grade)
- True dealer cost breakdown (invoice, holdback, dealer cash)
- Three negotiation targets: aggressive, reasonable, and likely
- Market context: days supply, price trends, active incentives for each model
- Section 179 tax calculator: estimate your first-year business vehicle deduction (GVWR-aware, pickup truck exemptions)
- VIN decoder with full vehicle specs
- Talking points for your negotiation

**DealHawk Pro adds:**
- Save vehicles and track deals across sessions
- Custom deal alerts -- get notified when listings match your criteria
- Priority support

**Supported sites:**
- CarGurus
- AutoTrader
- Cars.com
- Edmunds

**Privacy first:**
- No ads, no tracking, no data selling
- Card details never touch our servers (Stripe handles all payments)
- Only requests minimum browser permissions
- Full privacy policy: https://github.com/wbp318/DealHawk-MVP/blob/main/PRIVACY_POLICY.md

## Category
Shopping

## Language
English

## Permission Justifications

| Permission | Justification |
|-----------|---------------|
| `storage` | Caches API responses locally for faster repeat visits and stores authentication tokens |
| `sidePanel` | Displays the detailed deal analysis panel alongside listing pages |
| `activeTab` | Reads the current dealer listing page to extract vehicle data (price, VIN, days on lot) for scoring |

## Screenshots Needed

1. **CarGurus search results** -- Score badges overlaid on listing cards showing deal scores (e.g., 82/A, 61/C)
2. **Side panel analysis** -- Full deal breakdown showing score gauge, price table, offer targets, market context, and talking points
3. **Calculator tab** -- Manual MSRP-to-cost calculator with score result
4. **Tax tab** -- Section 179 calculator showing deduction, tax savings, and effective cost for a business truck
5. **Popup** -- Extension popup showing backend status, VIN lookup, and logged-in user with Pro badge
6. **Saved vehicles tab** -- List of saved vehicles with scores, prices, and dealer info

## Promotional Images Needed

- Small promo tile: 440x280
- Marquee promo tile: 1400x560

## Additional Notes

- Extension requires a running backend server (self-hosted or cloud deployment)
- Test card for Stripe: 4242 4242 4242 4242 (any future date, any CVC)
