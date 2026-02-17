"""
Dealer holdback rates by manufacturer.

Holdback is a hidden refund from the manufacturer to the dealer, typically
paid quarterly. It's calculated as a percentage of either MSRP or invoice.
This is part of the dealer's true cost that they won't voluntarily disclose.
"""

# Holdback as a percentage, and what it's based on
HOLDBACK_RATES: dict[str, dict] = {
    "Ram": {"rate": 0.03, "basis": "msrp"},
    "Dodge": {"rate": 0.03, "basis": "msrp"},
    "Jeep": {"rate": 0.03, "basis": "msrp"},
    "Chrysler": {"rate": 0.03, "basis": "msrp"},
    "Ford": {"rate": 0.03, "basis": "msrp"},
    "Lincoln": {"rate": 0.02, "basis": "msrp"},
    "Chevrolet": {"rate": 0.03, "basis": "invoice"},
    "GMC": {"rate": 0.03, "basis": "invoice"},
    "Buick": {"rate": 0.03, "basis": "invoice"},
    "Cadillac": {"rate": 0.03, "basis": "invoice"},
    "Toyota": {"rate": 0.02, "basis": "msrp"},
    "Nissan": {"rate": 0.03, "basis": "invoice"},
    "Honda": {"rate": 0.02, "basis": "msrp"},
    "Hyundai": {"rate": 0.02, "basis": "invoice"},
    "Kia": {"rate": 0.02, "basis": "invoice"},
}


def get_holdback(make: str, msrp: float, invoice: float) -> float:
    """Calculate the holdback amount for a given make and pricing."""
    info = HOLDBACK_RATES.get(make, {"rate": 0.02, "basis": "msrp"})
    basis_value = msrp if info["basis"] == "msrp" else invoice
    return round(basis_value * info["rate"], 2)
