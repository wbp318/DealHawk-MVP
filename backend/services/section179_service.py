"""
Section 179 tax deduction calculator.

Calculates first-year deduction, tax savings, effective cost, and optional
financing details for business vehicles. Vehicles over 6,000 lbs GVWR qualify
for enhanced deductions. Pickup trucks with 6ft+ beds are exempt from the
$32K heavy SUV cap.
"""

from backend.config.section179_data import (
    SECTION_179_LIMIT,
    BONUS_DEPRECIATION_RATE,
    HEAVY_SUV_CAP,
    GVWR_THRESHOLD,
    BUSINESS_USE_MINIMUM,
    LUXURY_AUTO_FIRST_YEAR_CAP,
    get_gvwr_info,
)


def calculate_section_179(
    vehicle_price: float,
    business_use_pct: float,
    tax_bracket: float,
    state_tax_rate: float = 0,
    down_payment: float = 0,
    loan_interest_rate: float = 0,
    loan_term_months: int = 60,
    model: str | None = None,
    gvwr_override: int | None = None,
) -> dict:
    """
    Calculate Section 179 deduction and tax savings.

    Returns a dict with qualification status, deduction amounts,
    tax savings, effective cost, and optional financing details.
    """
    # Check minimum business use
    if business_use_pct < BUSINESS_USE_MINIMUM:
        return {
            "qualifies": False,
            "reason": f"Business use must be at least {BUSINESS_USE_MINIMUM}%. "
                      f"You entered {business_use_pct}%.",
            "vehicle_price": vehicle_price,
            "business_use_pct": business_use_pct,
        }

    # Determine GVWR
    gvwr = gvwr_override
    gvwr_note = None
    is_pickup = False

    if gvwr_override:
        gvwr_note = "Using manually entered GVWR"
        # Still check model for pickup status even with manual GVWR
        info = get_gvwr_info(model)
        if info:
            is_pickup = info["is_pickup_6ft_bed"]
    else:
        info = get_gvwr_info(model)
        if info:
            gvwr = info["gvwr_min"]
            is_pickup = info["is_pickup_6ft_bed"]
            gvwr_note = f"Estimated GVWR range: {info['gvwr_min']:,}-{info['gvwr_max']:,} lbs"
        else:
            gvwr = None
            gvwr_note = "Model not in database. Enter GVWR manually for accurate calculation."

    # Determine deduction cap
    exceeds_gvwr = gvwr is not None and gvwr > GVWR_THRESHOLD
    cap_note = None

    if exceeds_gvwr and is_pickup:
        deduction_cap = SECTION_179_LIMIT
        cap_note = "Pickup truck with 6ft+ bed: exempt from $32K SUV cap. Full Section 179 limit applies."
    elif exceeds_gvwr:
        deduction_cap = HEAVY_SUV_CAP
        cap_note = f"Non-pickup vehicle over {GVWR_THRESHOLD:,} lbs: heavy SUV cap of ${HEAVY_SUV_CAP:,} applies."
    elif gvwr is not None:
        # Under GVWR threshold — IRC §280F luxury auto limits apply
        deduction_cap = LUXURY_AUTO_FIRST_YEAR_CAP
        cap_note = (
            f"Vehicle under {GVWR_THRESHOLD:,} lbs GVWR. "
            f"IRC §280F luxury auto limit of ${LUXURY_AUTO_FIRST_YEAR_CAP:,} applies (first year with bonus depreciation)."
        )
    else:
        # Unknown GVWR — assume pickup (conservative for truck-focused app)
        deduction_cap = SECTION_179_LIMIT
        cap_note = "GVWR unknown. Assuming full Section 179 eligibility — verify GVWR for accuracy."

    # Calculate deduction
    business_portion = vehicle_price * (business_use_pct / 100)
    first_year_deduction = min(business_portion, deduction_cap, SECTION_179_LIMIT)

    # Tax savings
    federal_savings = first_year_deduction * (tax_bracket / 100)
    state_savings = first_year_deduction * (state_tax_rate / 100)
    total_tax_savings = federal_savings + state_savings

    # Effective cost
    effective_cost = vehicle_price - total_tax_savings

    # Financing details (if financed)
    financing = None
    if loan_interest_rate > 0 and loan_term_months > 0:
        loan_amount = vehicle_price - down_payment
        if loan_amount > 0:
            monthly_rate = loan_interest_rate / 100 / 12
            monthly_payment = loan_amount * (
                monthly_rate * (1 + monthly_rate) ** loan_term_months
            ) / ((1 + monthly_rate) ** loan_term_months - 1)
            total_interest = (monthly_payment * loan_term_months) - loan_amount
            total_loan_cost = loan_amount + total_interest

            # Spread first-year tax benefit over 12 months for comparison
            monthly_tax_benefit = total_tax_savings / 12

            financing = {
                "down_payment": round(down_payment, 2),
                "loan_amount": round(loan_amount, 2),
                "monthly_payment": round(monthly_payment, 2),
                "total_interest": round(total_interest, 2),
                "total_loan_cost": round(total_loan_cost, 2),
                "monthly_tax_benefit": round(monthly_tax_benefit, 2),
                "effective_monthly_cost": round(monthly_payment - monthly_tax_benefit, 2),
            }
    elif loan_term_months > 0 and down_payment < vehicle_price:
        # 0% APR financing
        loan_amount = vehicle_price - down_payment
        if loan_amount > 0:
            monthly_payment = loan_amount / loan_term_months
            monthly_tax_benefit = total_tax_savings / 12

            financing = {
                "down_payment": round(down_payment, 2),
                "loan_amount": round(loan_amount, 2),
                "monthly_payment": round(monthly_payment, 2),
                "total_interest": 0,
                "total_loan_cost": round(loan_amount, 2),
                "monthly_tax_benefit": round(monthly_tax_benefit, 2),
                "effective_monthly_cost": round(monthly_payment - monthly_tax_benefit, 2),
            }

    return {
        "qualifies": True,
        "vehicle_price": vehicle_price,
        "business_use_pct": business_use_pct,
        "gvwr": gvwr,
        "gvwr_note": gvwr_note,
        "cap_note": cap_note,
        "first_year_deduction": round(first_year_deduction, 2),
        "federal_tax_savings": round(federal_savings, 2),
        "state_tax_savings": round(state_savings, 2),
        "total_tax_savings": round(total_tax_savings, 2),
        "effective_cost_after_tax": round(effective_cost, 2),
        "financing": financing,
        "tax_year": 2026,
        "section_179_limit": SECTION_179_LIMIT,
        "bonus_depreciation_rate": BONUS_DEPRECIATION_RATE,
    }
