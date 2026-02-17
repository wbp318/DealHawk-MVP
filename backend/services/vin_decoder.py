"""
VIN Decoder service using the free NHTSA vPIC API.
https://vpic.nhtsa.dot.gov/api/
"""

import httpx
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.models import Vehicle

settings = get_settings()

# Fields we care about from the NHTSA response
NHTSA_FIELD_MAP = {
    "Make": "make",
    "Model": "model",
    "Model Year": "year",
    "Trim": "trim",
    "Body Class": "body_class",
    "Drive Type": "drive_type",
    "Engine Number of Cylinders": "engine_cylinders",
    "Displacement (L)": "engine_displacement",
    "Engine Configuration": "engine_type",
    "Fuel Type - Primary": "fuel_type",
    "Gross Vehicle Weight Rating From": "gvwr",
    "Plant City": "plant_city",
    "Plant State": "plant_state",
    "Plant Country": "plant_country",
    "Manufacturer Name": "manufacturer",
}

INT_FIELDS = {"year", "engine_cylinders"}
FLOAT_FIELDS = {"engine_displacement"}


async def decode_vin(vin: str, db: Session | None = None) -> dict:
    """
    Decode a VIN using the NHTSA vPIC API.

    Returns a dict with vehicle specifications. Optionally caches in the
    database if a session is provided.
    """
    vin = vin.strip().upper()
    if len(vin) != 17:
        raise ValueError(f"VIN must be 17 characters, got {len(vin)}")

    # VINs only contain alphanumeric chars (excluding I, O, Q)
    import re
    if not re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', vin):
        raise ValueError("VIN contains invalid characters")

    # Check cache first
    if db:
        existing = db.get(Vehicle, vin)
        if existing:
            return _vehicle_to_dict(existing)

    # Call NHTSA API
    url = f"{settings.nhtsa_base_url}/vehicles/DecodeVinValues/{vin}?format=json"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    data = resp.json()
    results = data.get("Results", [{}])[0]

    # Parse into our format
    vehicle_data = {"vin": vin}
    for nhtsa_key, our_key in NHTSA_FIELD_MAP.items():
        value = results.get(nhtsa_key, "").strip()
        if not value or value == "Not Applicable":
            vehicle_data[our_key] = None
            continue

        if our_key in INT_FIELDS:
            try:
                vehicle_data[our_key] = int(float(value))
            except (ValueError, TypeError):
                vehicle_data[our_key] = None
        elif our_key in FLOAT_FIELDS:
            try:
                vehicle_data[our_key] = float(value)
            except (ValueError, TypeError):
                vehicle_data[our_key] = None
        else:
            vehicle_data[our_key] = value

    # Check for decode errors
    error_code = results.get("ErrorCode", "0")
    if error_code and error_code != "0":
        error_text = results.get("ErrorText", "Unknown decode error")
        # NHTSA returns errors as comma-separated codes; "0" means success
        # Partial decodes still return useful data, so we include errors but don't fail
        vehicle_data["decode_errors"] = error_text

    # Cache in database
    if db:
        vehicle = db.get(Vehicle, vin)
        if vehicle:
            for key, val in vehicle_data.items():
                if key not in ("vin", "decode_errors") and val is not None:
                    setattr(vehicle, key, val)
        else:
            filtered = {k: v for k, v in vehicle_data.items() if k != "decode_errors"}
            vehicle = Vehicle(**filtered)
            db.add(vehicle)
        db.commit()
        db.refresh(vehicle)

    return vehicle_data


def _vehicle_to_dict(vehicle: Vehicle) -> dict:
    """Convert a Vehicle ORM object to a plain dict."""
    return {
        "vin": vehicle.vin,
        "year": vehicle.year,
        "make": vehicle.make,
        "model": vehicle.model,
        "trim": vehicle.trim,
        "body_class": vehicle.body_class,
        "drive_type": vehicle.drive_type,
        "engine_cylinders": vehicle.engine_cylinders,
        "engine_displacement": vehicle.engine_displacement,
        "engine_type": vehicle.engine_type,
        "fuel_type": vehicle.fuel_type,
        "gvwr": vehicle.gvwr,
        "plant_city": vehicle.plant_city,
        "plant_state": vehicle.plant_state,
        "plant_country": vehicle.plant_country,
        "manufacturer": vehicle.manufacturer,
        "msrp": vehicle.msrp,
        "invoice_price": vehicle.invoice_price,
        "holdback": vehicle.holdback,
        "true_dealer_cost": vehicle.true_dealer_cost,
        "deal_score": vehicle.deal_score,
    }
