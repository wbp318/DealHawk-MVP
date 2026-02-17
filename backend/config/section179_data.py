"""
Section 179 tax deduction reference data for 2026.

Covers GVWR data for common trucks/SUVs to determine eligibility and
deduction caps. Vehicles over 6,000 lbs GVWR qualify for enhanced
Section 179 deductions. Pickup trucks with 6ft+ beds are exempt from
the $32K heavy SUV cap.
"""

# 2026 Section 179 limits (per IRS inflation adjustments + OBBBA restoration)
SECTION_179_LIMIT = 1_250_000  # 2025 indexed; verify IRS Rev. Proc. for 2026
BONUS_DEPRECIATION_RATE = 1.0  # 100% restored by One Big Beautiful Bill Act (2025)
HEAVY_SUV_CAP = 32_000
GVWR_THRESHOLD = 6_000  # lbs
BUSINESS_USE_MINIMUM = 50  # percent
LUXURY_AUTO_FIRST_YEAR_CAP = 20_400  # IRC §280F limit for vehicles under 6,000 lbs GVWR (with bonus depreciation)

# GVWR data by model
# is_pickup_6ft_bed: True = exempt from heavy SUV cap (full Section 179 applies)
MODEL_GVWR: dict[str, dict] = {
    # Ford
    "F-150": {"gvwr_min": 6100, "gvwr_max": 7850, "is_pickup_6ft_bed": True},
    "F-250": {"gvwr_min": 9900, "gvwr_max": 10400, "is_pickup_6ft_bed": True},
    "F-350": {"gvwr_min": 11200, "gvwr_max": 14000, "is_pickup_6ft_bed": True},
    "F-450": {"gvwr_min": 14000, "gvwr_max": 16500, "is_pickup_6ft_bed": True},
    # Ram
    "Ram 1500": {"gvwr_min": 6500, "gvwr_max": 7100, "is_pickup_6ft_bed": True},
    "Ram 2500": {"gvwr_min": 9000, "gvwr_max": 10000, "is_pickup_6ft_bed": True},
    "Ram 3500": {"gvwr_min": 11000, "gvwr_max": 14000, "is_pickup_6ft_bed": True},
    # Chevrolet
    "Silverado 1500": {"gvwr_min": 6600, "gvwr_max": 7400, "is_pickup_6ft_bed": True},
    "Silverado 2500HD": {"gvwr_min": 9500, "gvwr_max": 10650, "is_pickup_6ft_bed": True},
    "Silverado 3500HD": {"gvwr_min": 11000, "gvwr_max": 14000, "is_pickup_6ft_bed": True},
    # GMC
    "Sierra 1500": {"gvwr_min": 6600, "gvwr_max": 7400, "is_pickup_6ft_bed": True},
    "Sierra 2500HD": {"gvwr_min": 9500, "gvwr_max": 10650, "is_pickup_6ft_bed": True},
    "Sierra 3500HD": {"gvwr_min": 11000, "gvwr_max": 14000, "is_pickup_6ft_bed": True},
    # Toyota
    "Tundra": {"gvwr_min": 6400, "gvwr_max": 7200, "is_pickup_6ft_bed": True},
    "Tacoma": {"gvwr_min": 5400, "gvwr_max": 6100, "is_pickup_6ft_bed": True},
    # Nissan
    "Titan": {"gvwr_min": 7100, "gvwr_max": 8800, "is_pickup_6ft_bed": True},
    "Frontier": {"gvwr_min": 5500, "gvwr_max": 6200, "is_pickup_6ft_bed": True},
}


def get_gvwr_info(model: str | None) -> dict | None:
    """Look up GVWR info by model name with partial match fallback."""
    if not model:
        return None

    # Exact match
    info = MODEL_GVWR.get(model)
    if info:
        return info

    # Partial match (handles "Ram Ram 2500" → "Ram 2500")
    for key, val in MODEL_GVWR.items():
        if key in model or model in key:
            return val

    return None
