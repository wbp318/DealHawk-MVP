"""
Typical invoice-to-MSRP ratios by vehicle segment and make.

When we don't have exact invoice data, we estimate using these ratios.
Trucks typically have 5-10% markup from invoice to MSRP, with higher
trims and HD models having larger margins.
"""

# Invoice as a fraction of MSRP
INVOICE_RATIOS: dict[str, dict[str, float]] = {
    # Ford
    "Ford F-150": {"base": 0.93, "mid": 0.91, "high": 0.89},
    "Ford F-250": {"base": 0.93, "mid": 0.91, "high": 0.89},
    "Ford F-350": {"base": 0.93, "mid": 0.91, "high": 0.88},
    "Ford F-450": {"base": 0.92, "mid": 0.90, "high": 0.88},
    # Ram
    "Ram 1500": {"base": 0.92, "mid": 0.90, "high": 0.88},
    "Ram 2500": {"base": 0.92, "mid": 0.90, "high": 0.88},
    "Ram 3500": {"base": 0.92, "mid": 0.90, "high": 0.87},
    # GM
    "Chevrolet Silverado 1500": {"base": 0.93, "mid": 0.91, "high": 0.89},
    "Chevrolet Silverado 2500HD": {"base": 0.92, "mid": 0.90, "high": 0.88},
    "Chevrolet Silverado 3500HD": {"base": 0.92, "mid": 0.90, "high": 0.87},
    "GMC Sierra 1500": {"base": 0.92, "mid": 0.90, "high": 0.88},
    "GMC Sierra 2500HD": {"base": 0.92, "mid": 0.90, "high": 0.88},
    "GMC Sierra 3500HD": {"base": 0.92, "mid": 0.90, "high": 0.87},
    # Toyota
    "Toyota Tundra": {"base": 0.94, "mid": 0.92, "high": 0.91},
    "Toyota Tacoma": {"base": 0.95, "mid": 0.93, "high": 0.92},
    # Nissan
    "Nissan Titan": {"base": 0.92, "mid": 0.90, "high": 0.88},
    "Nissan Frontier": {"base": 0.94, "mid": 0.92, "high": 0.90},
}

# Default ratio when we don't have specific data
DEFAULT_INVOICE_RATIO = 0.92

# MSRP ranges for trim classification
# Under this MSRP = base, under the high = mid, above = high
TRIM_THRESHOLDS: dict[str, dict[str, int]] = {
    "F-150": {"base_max": 42000, "high_min": 65000},
    "F-250": {"base_max": 50000, "high_min": 75000},
    "F-350": {"base_max": 52000, "high_min": 80000},
    "Ram 1500": {"base_max": 42000, "high_min": 60000},
    "Ram 2500": {"base_max": 48000, "high_min": 72000},
    "Ram 3500": {"base_max": 50000, "high_min": 78000},
    "Silverado 1500": {"base_max": 42000, "high_min": 62000},
    "Silverado 2500HD": {"base_max": 48000, "high_min": 72000},
    "Sierra 1500": {"base_max": 44000, "high_min": 65000},
    "Sierra 2500HD": {"base_max": 50000, "high_min": 75000},
}


def estimate_invoice(make: str, model: str, msrp: float) -> float:
    """Estimate invoice price from MSRP using known ratios."""
    # Try "Make Model" first, then just "Model" (handles "Ram Ram 2500" vs "Ram 2500")
    ratios = INVOICE_RATIOS.get(f"{make} {model}") or INVOICE_RATIOS.get(model)

    if ratios:
        thresholds = TRIM_THRESHOLDS.get(model, {"base_max": 45000, "high_min": 70000})
        if msrp <= thresholds["base_max"]:
            ratio = ratios["base"]
        elif msrp >= thresholds["high_min"]:
            ratio = ratios["high"]
        else:
            ratio = ratios["mid"]
    else:
        ratio = DEFAULT_INVOICE_RATIO

    return round(msrp * ratio, 2)
