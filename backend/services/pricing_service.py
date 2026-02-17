"""
Pricing service - looks up or estimates invoice price, holdback, and true dealer cost.
"""

from sqlalchemy.orm import Session

from backend.config.holdback_rates import get_holdback
from backend.config.invoice_ranges import estimate_invoice
from backend.database.models import InvoicePriceCache


def get_pricing(
    year: int,
    make: str,
    model: str,
    msrp: float,
    trim: str | None = None,
    dealer_cash: float = 0,
    db: Session | None = None,
) -> dict:
    """
    Look up or estimate the true dealer cost for a vehicle.

    Returns:
        {
            "msrp": float,
            "invoice_price": float,
            "holdback": float,
            "dealer_cash": float,
            "true_dealer_cost": float,
            "margin_from_msrp": float,
            "margin_pct": float,
            "source": str,  # "cached" or "estimated"
        }
    """
    invoice = None
    holdback_amount = None
    source = "estimated"

    # Try to find cached invoice data
    if db:
        query = db.query(InvoicePriceCache).filter(
            InvoicePriceCache.year == year,
            InvoicePriceCache.make == make,
            InvoicePriceCache.model == model,
        )
        if trim:
            query = query.filter(InvoicePriceCache.trim == trim)
        cached = query.first()
        if cached:
            invoice = cached.invoice_price
            holdback_amount = cached.holdback_amount
            source = "cached"

    # Estimate if not cached
    if invoice is None:
        invoice = estimate_invoice(make, model, msrp)
    if holdback_amount is None:
        holdback_amount = get_holdback(make, msrp, invoice)

    true_cost = invoice - holdback_amount - dealer_cash
    margin = msrp - true_cost
    margin_pct = (margin / msrp * 100) if msrp > 0 else 0

    return {
        "msrp": msrp,
        "invoice_price": round(invoice, 2),
        "holdback": round(holdback_amount, 2),
        "dealer_cash": dealer_cash,
        "true_dealer_cost": round(true_cost, 2),
        "margin_from_msrp": round(margin, 2),
        "margin_pct": round(margin_pct, 1),
        "source": source,
    }
