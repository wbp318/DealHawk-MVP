"""
Deal scoring engine - the core product value of DealHawk.

5-factor weighted scoring (0-100):
  1. Price vs True Dealer Cost  (35%)
  2. Days on Lot                (25%)
  3. Available Incentives       (20%)
  4. Market Supply              (12%)
  5. Timing / Seasonal          (8%)
"""

from datetime import date, datetime
from dataclasses import dataclass, field

from backend.services.pricing_service import get_pricing

# Industry average days supply
INDUSTRY_AVG_DAYS_SUPPLY = 76

# Known days supply by model (February 2026 data from TRUCK_BUYING_GUIDE.md)
MODEL_DAYS_SUPPLY: dict[str, int] = {
    "Ram 3500": 342,
    "Ram 2500": 318,
    "Ram 1500": 120,
    "F-150": 100,
    "F-250": 90,
    "F-350": 85,
    "F-450": 60,
    "Sierra 1500": 85,
    "Sierra 2500HD": 80,
    "Silverado 1500": 85,
    "Silverado 2500HD": 80,
    "Tundra": 33,
    "Tacoma": 30,
}

# Floor plan carrying cost per day (average from research)
CARRYING_COST_PER_DAY = 7.90


@dataclass
class ScoreBreakdown:
    total_score: int
    price_score: float
    price_weight: float = 0.35
    days_score: float = 0
    days_weight: float = 0.25
    incentive_score: float = 0
    incentive_weight: float = 0.20
    supply_score: float = 0
    supply_weight: float = 0.12
    timing_score: float = 0
    timing_weight: float = 0.08
    details: dict = field(default_factory=dict)


@dataclass
class OfferTargets:
    aggressive: float  # Lowest realistic offer
    reasonable: float  # Fair starting negotiation point
    likely: float      # What you'll probably settle at
    carrying_costs: float  # Dealer's estimated carrying costs
    details: dict = field(default_factory=dict)


def score_deal(
    asking_price: float,
    msrp: float,
    make: str,
    model: str,
    year: int,
    days_on_lot: int = 0,
    dealer_cash: float = 0,
    rebates_available: float = 0,
    trim: str | None = None,
    score_date: date | None = None,
) -> dict:
    """
    Score a vehicle deal from 0-100.

    Higher scores = better deal for the buyer.
    """
    if score_date is None:
        score_date = date.today()

    # Get pricing data
    pricing = get_pricing(year, make, model, msrp, trim=trim, dealer_cash=dealer_cash)
    true_cost = pricing["true_dealer_cost"]

    # --- Factor 1: Price vs True Dealer Cost (35%) ---
    price_score = _score_price(asking_price, true_cost, msrp)

    # --- Factor 2: Days on Lot (25%) ---
    days_score = _score_days_on_lot(days_on_lot)

    # --- Factor 3: Available Incentives (20%) ---
    incentive_score = _score_incentives(rebates_available, msrp)

    # --- Factor 4: Market Supply (12%) ---
    supply_score = _score_market_supply(make, model)

    # --- Factor 5: Timing / Seasonal (8%) ---
    timing_score = _score_timing(score_date)

    # Weighted total
    total = (
        price_score * 0.35
        + days_score * 0.25
        + incentive_score * 0.20
        + supply_score * 0.12
        + timing_score * 0.08
    )
    total_score = min(100, max(0, round(total)))

    # Generate offer targets
    offers = _calculate_offers(asking_price, true_cost, msrp, days_on_lot, rebates_available)

    breakdown = ScoreBreakdown(
        total_score=total_score,
        price_score=round(price_score, 1),
        days_score=round(days_score, 1),
        incentive_score=round(incentive_score, 1),
        supply_score=round(supply_score, 1),
        timing_score=round(timing_score, 1),
        details={
            "asking_price": asking_price,
            "true_dealer_cost": true_cost,
            "price_vs_cost_pct": round((asking_price - true_cost) / true_cost * 100, 1) if true_cost else 0,
        },
    )

    return {
        "score": total_score,
        "grade": _score_to_grade(total_score),
        "breakdown": {
            "price": {"score": breakdown.price_score, "weight": "35%", "max": 100},
            "days_on_lot": {"score": breakdown.days_score, "weight": "25%", "max": 100},
            "incentives": {"score": breakdown.incentive_score, "weight": "20%", "max": 100},
            "market_supply": {"score": breakdown.supply_score, "weight": "12%", "max": 100},
            "timing": {"score": breakdown.timing_score, "weight": "8%", "max": 100},
        },
        "pricing": pricing,
        "offers": {
            "aggressive": round(offers.aggressive, 2),
            "reasonable": round(offers.reasonable, 2),
            "likely": round(offers.likely, 2),
            "carrying_costs": round(offers.carrying_costs, 2),
        },
    }


def _score_price(asking: float, true_cost: float, msrp: float) -> float:
    """Score based on how close asking price is to true dealer cost."""
    if true_cost <= 0 or msrp <= 0:
        return 50  # No data, neutral score

    margin = msrp - true_cost
    if margin <= 0:
        return 50

    # How much of the margin is the buyer capturing?
    buyer_savings = msrp - asking
    capture_pct = buyer_savings / margin * 100

    if asking <= true_cost:
        return 100  # Below dealer cost = perfect
    elif capture_pct >= 80:
        return 90
    elif capture_pct >= 60:
        return 75
    elif capture_pct >= 40:
        return 55
    elif capture_pct >= 20:
        return 35
    elif capture_pct >= 0:
        return 15
    else:
        return 5  # Above MSRP


def _score_days_on_lot(days: int) -> float:
    """Score based on how long the vehicle has been sitting. More days = better for buyer."""
    if days >= 270:
        return 100
    elif days >= 180:
        return 80
    elif days >= 120:
        return 65
    elif days >= 90:
        return 50
    elif days >= 60:
        return 35
    elif days >= 30:
        return 20
    else:
        return 10


def _score_incentives(rebates: float, msrp: float) -> float:
    """Score based on available rebates as a percentage of MSRP."""
    if msrp <= 0:
        return 0
    pct = rebates / msrp * 100

    if pct >= 15:
        return 100
    elif pct >= 10:
        return 85
    elif pct >= 7:
        return 70
    elif pct >= 5:
        return 55
    elif pct >= 3:
        return 40
    elif pct >= 1:
        return 25
    else:
        return 10


def _score_market_supply(make: str, model: str) -> float:
    """Score based on model's days supply vs industry average."""
    # Try exact match, then partial match
    days_supply = MODEL_DAYS_SUPPLY.get(model)
    if days_supply is None:
        for key, val in MODEL_DAYS_SUPPLY.items():
            if key in model or model in key:
                days_supply = val
                break

    if days_supply is None:
        return 40  # Unknown, slightly below neutral

    ratio = days_supply / INDUSTRY_AVG_DAYS_SUPPLY
    if ratio >= 4:
        return 100  # 4x+ industry avg (Ram 2500/3500 territory)
    elif ratio >= 2.5:
        return 85
    elif ratio >= 1.5:
        return 65
    elif ratio >= 1.0:
        return 45
    elif ratio >= 0.7:
        return 25
    else:
        return 10  # Below average supply = no leverage


def _score_timing(d: date) -> float:
    """Score based on time of month/quarter/year."""
    score = 30  # Base

    day = d.day
    month = d.month

    # Last 5 days of month
    if day >= 26:
        score += 30
    elif day >= 20:
        score += 15

    # Quarter-end months (March, June, September, December)
    if month in (3, 6, 9, 12):
        score += 25

    # Year-end (December)
    if month == 12:
        score += 15

    return min(100, score)


def _calculate_offers(
    asking: float,
    true_cost: float,
    msrp: float,
    days_on_lot: int,
    rebates: float,
) -> OfferTargets:
    """Generate three offer targets based on deal analysis."""
    carrying_costs = days_on_lot * CARRYING_COST_PER_DAY

    # Discount percentages based on days on lot (from TRUCK_BUYING_GUIDE.md)
    if days_on_lot >= 300:
        aggressive_pct, reasonable_pct, likely_pct = 0.28, 0.23, 0.20
    elif days_on_lot >= 180:
        aggressive_pct, reasonable_pct, likely_pct = 0.23, 0.18, 0.15
    elif days_on_lot >= 90:
        aggressive_pct, reasonable_pct, likely_pct = 0.17, 0.13, 0.10
    elif days_on_lot >= 60:
        aggressive_pct, reasonable_pct, likely_pct = 0.12, 0.09, 0.07
    else:
        aggressive_pct, reasonable_pct, likely_pct = 0.10, 0.07, 0.05

    aggressive = msrp * (1 - aggressive_pct) - rebates
    reasonable = msrp * (1 - reasonable_pct) - rebates
    likely = msrp * (1 - likely_pct) - rebates

    # Floor: never offer below true cost minus carrying costs (dealer's breakeven)
    floor = true_cost - carrying_costs
    aggressive = max(aggressive, floor)
    reasonable = max(reasonable, floor)
    likely = max(likely, floor)

    return OfferTargets(
        aggressive=aggressive,
        reasonable=reasonable,
        likely=likely,
        carrying_costs=carrying_costs,
        details={
            "aggressive_discount_pct": aggressive_pct * 100,
            "reasonable_discount_pct": reasonable_pct * 100,
            "likely_discount_pct": likely_pct * 100,
            "floor_price": round(floor, 2),
        },
    )


def _score_to_grade(score: int) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C+"
    elif score >= 40:
        return "C"
    elif score >= 30:
        return "D"
    else:
        return "F"
