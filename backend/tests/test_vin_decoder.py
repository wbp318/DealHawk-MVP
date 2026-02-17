"""Tests for the VIN decoder service."""

import pytest
import pytest_asyncio
from backend.services.vin_decoder import decode_vin


@pytest.mark.asyncio
async def test_decode_ram_vin():
    """Test decoding a Ram 2500 VIN via NHTSA API."""
    # This is a real VIN pattern for a Ram 2500
    result = await decode_vin("3C6UR5DL1PG612345")
    assert result["vin"] == "3C6UR5DL1PG612345"
    assert result["make"] is not None
    # NHTSA should return Ram/Stellantis for 3C6 prefix
    assert "year" in result


@pytest.mark.asyncio
async def test_decode_ford_vin():
    """Test decoding a Ford F-150 VIN via NHTSA API."""
    result = await decode_vin("1FTFW1E80PFA12345")
    assert result["vin"] == "1FTFW1E80PFA12345"
    assert result["make"] is not None


@pytest.mark.asyncio
async def test_invalid_vin_length():
    """VIN must be 17 characters."""
    with pytest.raises(ValueError, match="17 characters"):
        await decode_vin("ABC123")


@pytest.mark.asyncio
async def test_vin_uppercased():
    """VIN should be uppercased automatically."""
    result = await decode_vin("1ftfw1e80pfa12345")
    assert result["vin"] == "1FTFW1E80PFA12345"


@pytest.mark.asyncio
async def test_decode_returns_expected_fields():
    """Decoded VIN should include all expected fields."""
    result = await decode_vin("1FTFW1E80PFA12345")
    expected_fields = [
        "vin", "year", "make", "model", "trim", "body_class",
        "drive_type", "engine_cylinders", "engine_displacement",
        "fuel_type", "gvwr", "plant_country",
    ]
    for field in expected_fields:
        assert field in result, f"Missing field: {field}"
