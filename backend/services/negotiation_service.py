"""
Negotiation service - generates offer targets and talking points.

Uses dealer economics (floor plan costs, curtailment, holdback) to produce
specific dollar amounts and scripts a buyer can use at the dealership.
"""

from backend.services.deal_scorer import CARRYING_COST_PER_DAY


def generate_negotiation_brief(
    asking_price: float,
    msrp: float,
    invoice_price: float,
    holdback: float,
    true_dealer_cost: float,
    days_on_lot: int,
    rebates_available: float = 0,
    make: str = "",
    model: str = "",
    year: int = 0,
) -> dict:
    """
    Generate a full negotiation brief with talking points, offer targets,
    and dealer cost analysis.
    """
    carrying_costs = round(days_on_lot * CARRYING_COST_PER_DAY, 2)

    # Curtailment estimate: 5-20% of invoice after 90 days
    curtailment = 0
    if days_on_lot > 90:
        if days_on_lot > 180:
            curtailment = round(invoice_price * 0.15, 2)
        elif days_on_lot > 120:
            curtailment = round(invoice_price * 0.10, 2)
        else:
            curtailment = round(invoice_price * 0.05, 2)

    # Total dealer pain = carrying costs + curtailment
    total_dealer_cost_to_hold = carrying_costs + curtailment

    # Breakeven for dealer
    dealer_breakeven = true_dealer_cost - total_dealer_cost_to_hold

    # Offer targets
    aggressive_offer = max(dealer_breakeven, true_dealer_cost * 0.95)
    reasonable_offer = true_dealer_cost
    likely_settlement = round((true_dealer_cost + asking_price) * 0.45, 2)  # Weighted toward dealer cost

    # The asking price vs our targets
    asking_vs_invoice = round(asking_price - invoice_price, 2)
    asking_vs_true_cost = round(asking_price - true_dealer_cost, 2)

    # Talking points
    talking_points = _build_talking_points(
        asking_price=asking_price,
        msrp=msrp,
        invoice_price=invoice_price,
        true_dealer_cost=true_dealer_cost,
        days_on_lot=days_on_lot,
        carrying_costs=carrying_costs,
        curtailment=curtailment,
        rebates_available=rebates_available,
        make=make,
        model=model,
        year=year,
    )

    return {
        "dealer_economics": {
            "invoice_price": invoice_price,
            "holdback": holdback,
            "true_dealer_cost": true_dealer_cost,
            "carrying_costs": carrying_costs,
            "curtailment_estimate": curtailment,
            "total_cost_to_hold": total_dealer_cost_to_hold,
            "dealer_breakeven": round(dealer_breakeven, 2),
            "asking_vs_invoice": asking_vs_invoice,
            "asking_vs_true_cost": asking_vs_true_cost,
            "dealer_margin_at_asking": asking_vs_true_cost,
        },
        "offer_targets": {
            "aggressive": round(aggressive_offer, 2),
            "reasonable": round(reasonable_offer, 2),
            "likely_settlement": round(likely_settlement, 2),
        },
        "talking_points": talking_points,
        "rebates_available": rebates_available,
    }


def _build_talking_points(
    asking_price: float,
    msrp: float,
    invoice_price: float,
    true_dealer_cost: float,
    days_on_lot: int,
    carrying_costs: float,
    curtailment: float,
    rebates_available: float,
    make: str,
    model: str,
    year: int,
) -> list[dict]:
    """Build a list of negotiation talking points with scripts."""
    points = []

    # Floor plan costs
    if days_on_lot > 30:
        points.append({
            "category": "Floor Plan Costs",
            "leverage": "high" if days_on_lot > 90 else "medium",
            "point": f"This {year} {make} {model} has been on your lot for {days_on_lot} days. "
                     f"At roughly $7.90/day in floor plan interest, that's approximately "
                     f"${carrying_costs:,.0f} in carrying costs alone.",
            "script": f'"I know this truck has been here for {days_on_lot} days. '
                      f'The floor plan costs on that have to be significant. '
                      f'I\'d like to help you move it today."',
        })

    # Curtailment
    if curtailment > 0:
        points.append({
            "category": "Curtailment Pressure",
            "leverage": "high",
            "point": f"After 90 days, your floor plan lender likely requires curtailment payments. "
                     f"Estimated curtailment on this unit: ${curtailment:,.0f}.",
            "script": '"I understand that units past 90 days start triggering curtailment. '
                      'Let\'s find a number that works for both of us so we can close this today."',
        })

    # Invoice vs asking
    asking_above_invoice = asking_price - invoice_price
    if asking_above_invoice > 0:
        points.append({
            "category": "Invoice Reference",
            "leverage": "medium",
            "point": f"The asking price is ${asking_above_invoice:,.0f} above invoice. "
                     f"With holdback and dealer cash, your actual cost is closer to "
                     f"${true_dealer_cost:,.0f}.",
            "script": f'"I\'ve done my research and I know the invoice on this truck is around '
                      f'${invoice_price:,.0f}. With holdback, your true cost is lower than that. '
                      f'I\'m looking for a fair deal for both of us."',
        })

    # Rebates
    if rebates_available > 0:
        points.append({
            "category": "Available Rebates",
            "leverage": "medium",
            "point": f"There are ${rebates_available:,.0f} in manufacturer rebates/incentives "
                     f"available on this model right now.",
            "script": f'"I want to make sure I\'m getting all available incentives. '
                      f'I see there\'s up to ${rebates_available:,.0f} in current rebates for this model. '
                      f'Can you walk me through which ones apply to this VIN?"',
        })

    # Competing quotes
    points.append({
        "category": "Competing Offers",
        "leverage": "high",
        "point": "Always mention you're getting quotes from multiple dealers.",
        "script": '"I\'m looking at similar trucks at two other dealerships in the area. '
                  'I\'d prefer to buy from you, but I need the numbers to make sense. '
                  'What\'s your best out-the-door price?"',
    })

    # Month-end pressure
    points.append({
        "category": "Closing Today",
        "leverage": "medium",
        "point": "Signal that you're a serious buyer ready to close immediately.",
        "script": '"I\'m ready to sign today if we can agree on a number. '
                  'I have financing arranged. What can you do for me?"',
    })

    return points
