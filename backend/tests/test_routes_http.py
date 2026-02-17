"""HTTP-layer tests for consumer API endpoints: negotiate, pricing, incentives, VIN."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, AsyncMock
from datetime import date

from backend.database.models import Base, IncentiveProgram, InvoicePriceCache


@pytest.fixture
def test_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return TestSession


@pytest.fixture
def client(test_session):
    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def seeded_client(test_session):
    """Client with incentive and invoice data seeded."""
    db = test_session()
    db.add(IncentiveProgram(
        make="Ram", model="Ram 2500", year=2026,
        incentive_type="cash_back", name="Ram Cash Back",
        amount=7000, region="national",
        start_date=date(2026, 2, 1), end_date=date(2026, 3, 31),
    ))
    db.add(IncentiveProgram(
        make="Ford", model="F-150", year=2026,
        incentive_type="apr", name="Ford 0% APR",
        amount=0, apr_rate=0.0, apr_months=60, region="national",
        start_date=date(2026, 2, 1), end_date=date(2026, 3, 31),
    ))
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


class TestNegotiateEndpoint:

    def test_negotiate_returns_200(self, client):
        resp = client.post("/api/v1/negotiate", json={
            "asking_price": 55000,
            "msrp": 65000,
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "days_on_lot": 120,
            "rebates_available": 7000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "dealer_economics" in data
        assert "offer_targets" in data
        assert "talking_points" in data

    def test_negotiate_offer_targets(self, client):
        """Offer targets should be present with all keys."""
        resp = client.post("/api/v1/negotiate", json={
            "asking_price": 70000,
            "msrp": 80000,
            "make": "Ford",
            "model": "F-250",
            "year": 2026,
            "days_on_lot": 90,
        })
        data = resp.json()
        targets = data["offer_targets"]
        assert "aggressive" in targets
        assert "reasonable" in targets
        assert "likely_settlement" in targets
        assert all(v > 0 for v in targets.values())

    def test_negotiate_validation_rejects_bad_input(self, client):
        """Missing required fields should return 422."""
        resp = client.post("/api/v1/negotiate", json={
            "asking_price": 55000,
            # missing msrp, make, model, year
        })
        assert resp.status_code == 422


class TestPricingEndpoint:

    def test_pricing_returns_200(self, client):
        resp = client.get("/api/v1/pricing/2026/Ford/F-150?msrp=55000")
        assert resp.status_code == 200
        data = resp.json()
        assert "invoice_price" in data
        assert "holdback" in data
        assert "true_dealer_cost" in data

    def test_pricing_missing_msrp(self, client):
        """msrp=0 should return 400."""
        resp = client.get("/api/v1/pricing/2026/Ford/F-150?msrp=0")
        assert resp.status_code == 400
        assert "msrp" in resp.json()["detail"].lower()

    def test_pricing_no_msrp_param(self, client):
        """No msrp query param (defaults to 0) should return 400."""
        resp = client.get("/api/v1/pricing/2026/Ford/F-150")
        assert resp.status_code == 400


class TestIncentivesEndpoint:

    def test_incentives_returns_list(self, seeded_client):
        resp = seeded_client.get("/api/v1/incentives/Ram")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["make"] == "Ram"

    def test_incentives_model_filter(self, seeded_client):
        resp = seeded_client.get("/api/v1/incentives/Ram?model=Ram%202500")
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["model"] == "Ram 2500" for i in data)

    def test_incentives_empty_for_unknown_make(self, seeded_client):
        resp = seeded_client.get("/api/v1/incentives/UnknownMake")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_incentives_no_auth_required(self, client):
        """Incentives endpoint works without auth."""
        resp = client.get("/api/v1/incentives/Ford")
        assert resp.status_code == 200


class TestVINEndpoint:

    @patch("backend.api.routes.decode_vin", new_callable=AsyncMock)
    def test_vin_decode_success(self, mock_decode, client):
        mock_decode.return_value = {
            "vin": "1C6SRFFT5PN123456",
            "make": "Ram",
            "model": "2500",
            "year": 2023,
        }
        resp = client.get("/api/v1/vin/1C6SRFFT5PN123456")
        assert resp.status_code == 200
        assert resp.json()["make"] == "Ram"

    @patch("backend.api.routes.decode_vin", new_callable=AsyncMock)
    def test_vin_decode_invalid_vin(self, mock_decode, client):
        mock_decode.side_effect = ValueError("VIN must be 17 characters")
        resp = client.get("/api/v1/vin/BADVIN")
        assert resp.status_code == 400

    @patch("backend.api.routes.decode_vin", new_callable=AsyncMock)
    def test_vin_decode_upstream_error(self, mock_decode, client):
        """Upstream failure should return 502, not expose internals."""
        mock_decode.side_effect = Exception("Connection refused")
        resp = client.get("/api/v1/vin/1C6SRFFT5PN123456")
        assert resp.status_code == 502
        assert "upstream" in resp.json()["detail"].lower()
        # Should NOT contain the raw exception message
        assert "Connection refused" not in resp.json()["detail"]
