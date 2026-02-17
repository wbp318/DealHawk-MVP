"""Tests for VIN decoder DB caching (write, cache hit, update)."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.models import Base, Vehicle
from backend.services.vin_decoder import decode_vin


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return TestSession


NHTSA_RESPONSE = {
    "Results": [{
        "Make": "Ram",
        "Model": "2500",
        "Model Year": "2023",
        "Trim": "Laramie",
        "Body Class": "Pickup",
        "Drive Type": "4WD",
        "Engine Number of Cylinders": "8",
        "Displacement (L)": "6.7",
        "Fuel Type - Primary": "Diesel",
        "Gross Vehicle Weight Rating From": "10000",
        "ErrorCode": "0",
    }]
}


@pytest.mark.asyncio
class TestVINDecoderDB:

    @patch("backend.services.vin_decoder.httpx.AsyncClient")
    async def test_decode_writes_to_db(self, mock_client_cls, db_session):
        """First decode should store vehicle in database."""
        mock_response = MagicMock()
        mock_response.json.return_value = NHTSA_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        db = db_session()
        result = await decode_vin("1C6SRFFT5PN123456", db=db)

        assert result["make"] == "Ram"
        assert result["model"] == "2500"

        # Verify it was written to DB
        vehicle = db.get(Vehicle, "1C6SRFFT5PN123456")
        assert vehicle is not None
        assert vehicle.make == "Ram"
        assert vehicle.model == "2500"
        db.close()

    @patch("backend.services.vin_decoder.httpx.AsyncClient")
    async def test_cache_hit_skips_api(self, mock_client_cls, db_session):
        """Second decode for same VIN should return from DB without API call."""
        # Pre-seed vehicle in DB
        db = db_session()
        vehicle = Vehicle(
            vin="1C6SRFFT5PN123456",
            make="Ram",
            model="2500",
            year=2023,
            trim="Laramie",
        )
        db.add(vehicle)
        db.commit()

        result = await decode_vin("1C6SRFFT5PN123456", db=db)
        assert result["make"] == "Ram"
        assert result["model"] == "2500"

        # API should NOT have been called
        mock_client_cls.assert_not_called()
        db.close()

    @patch("backend.services.vin_decoder.httpx.AsyncClient")
    async def test_update_existing_vehicle(self, mock_client_cls, db_session):
        """The update path in vin_decoder.py (lines 99-103) merges API data into
        an existing Vehicle row. This happens when a VIN is not found at the
        initial cache check (line 55) but exists by the time the API returns
        (race condition) OR when decode_vin is called without db first then with db.

        We test this by directly calling the update branch: insert a partial
        Vehicle, mock db.get to return None on first call (cache miss) then
        the Vehicle on second call (post-API write), so the setattr update path
        is exercised.
        """
        db = db_session()
        # Pre-seed a partial vehicle (no trim, no drive_type)
        vehicle = Vehicle(
            vin="1FTFW1E50NFA12345",
            make="Ford",
            model="F-150",
            year=2022,
        )
        db.add(vehicle)
        db.commit()
        assert vehicle.trim is None

        # Simulate API returning enriched data with trim
        updated_response = {
            "Results": [{
                "Make": "Ford",
                "Model": "F-150",
                "Model Year": "2022",
                "Trim": "Lariat",
                "Body Class": "Pickup",
                "Drive Type": "4WD",
                "ErrorCode": "0",
            }]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = updated_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Patch db.get to simulate: cache miss on first call, then vehicle found
        # on second call (the post-API-call check at line 99).
        original_get = db.get
        call_count = {"n": 0}

        def mock_db_get(model_cls, pk):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # Cache miss — forces API call
            return original_get(model_cls, pk)  # Second call finds existing

        with patch.object(db, "get", side_effect=mock_db_get):
            result = await decode_vin("1FTFW1E50NFA12345", db=db)

        # The API was called (cache miss path)
        mock_client.get.assert_called_once()

        # The vehicle should have been UPDATED with trim from API data
        db.refresh(vehicle)
        assert vehicle.trim == "Lariat"
        assert vehicle.drive_type == "4WD"
        # Original data preserved
        assert vehicle.make == "Ford"
        assert vehicle.model == "F-150"
        assert vehicle.year == 2022
        db.close()
