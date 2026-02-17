"""Tests for Section 179 tax deduction calculator."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base
from backend.services.section179_service import calculate_section_179


@pytest.fixture
def client():
    """Create a test client with an isolated in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with patch("backend.database.db.SessionLocal", TestSession):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


class TestSection179Service:
    """Test the Section 179 calculation logic directly."""

    def test_full_business_use_f250(self):
        """$70K F-250, 100% business use, 37% bracket → full deduction."""
        result = calculate_section_179(
            vehicle_price=70000,
            business_use_pct=100,
            tax_bracket=37,
            model="F-250",
        )
        assert result["qualifies"] is True
        assert result["first_year_deduction"] == 70000
        assert result["federal_tax_savings"] == 25900
        assert result["total_tax_savings"] == 25900
        assert result["effective_cost_after_tax"] == 44100

    def test_partial_business_use(self):
        """75% business use → proportionally reduced deduction."""
        result = calculate_section_179(
            vehicle_price=60000,
            business_use_pct=75,
            tax_bracket=37,
            model="Ram 2500",
        )
        assert result["qualifies"] is True
        assert result["first_year_deduction"] == 45000  # 60000 * 0.75
        assert result["federal_tax_savings"] == 16650  # 45000 * 0.37

    def test_below_50_pct_disqualified(self):
        """40% business use → does not qualify."""
        result = calculate_section_179(
            vehicle_price=70000,
            business_use_pct=40,
            tax_bracket=37,
            model="F-250",
        )
        assert result["qualifies"] is False
        assert "50%" in result["reason"]

    def test_state_tax_savings(self):
        """State tax rate adds to total savings."""
        result = calculate_section_179(
            vehicle_price=70000,
            business_use_pct=100,
            tax_bracket=37,
            state_tax_rate=5,
            model="F-250",
        )
        assert result["qualifies"] is True
        assert result["federal_tax_savings"] == 25900
        assert result["state_tax_savings"] == 3500  # 70000 * 0.05
        assert result["total_tax_savings"] == 29400

    def test_heavy_suv_cap_applies(self):
        """Non-pickup with GVWR > 6K → $32K cap."""
        result = calculate_section_179(
            vehicle_price=80000,
            business_use_pct=100,
            tax_bracket=37,
            model=None,
            gvwr_override=7000,
        )
        # GVWR override with no model info → not identified as pickup
        assert result["qualifies"] is True
        # With gvwr_override but no model, it can't determine is_pickup
        # so it should apply the SUV cap
        assert result["first_year_deduction"] == 32000
        assert "SUV cap" in (result["cap_note"] or "")

    def test_pickup_exempt_from_suv_cap(self):
        """Known pickup truck (F-250) → no cap, full deduction."""
        result = calculate_section_179(
            vehicle_price=80000,
            business_use_pct=100,
            tax_bracket=37,
            model="F-250",
        )
        assert result["qualifies"] is True
        assert result["first_year_deduction"] == 80000
        assert "exempt" in (result["cap_note"] or "").lower()

    def test_financing_calculation(self):
        """Financing with interest shows monthly details."""
        result = calculate_section_179(
            vehicle_price=70000,
            business_use_pct=100,
            tax_bracket=37,
            down_payment=10000,
            loan_interest_rate=6.0,
            loan_term_months=60,
            model="F-250",
        )
        assert result["qualifies"] is True
        assert result["financing"] is not None
        fin = result["financing"]
        assert fin["down_payment"] == 10000
        assert fin["loan_amount"] == 60000
        assert fin["monthly_payment"] > 0
        assert fin["total_interest"] > 0
        assert fin["monthly_tax_benefit"] > 0

    def test_zero_apr_financing(self):
        """0% APR → no interest."""
        result = calculate_section_179(
            vehicle_price=60000,
            business_use_pct=100,
            tax_bracket=37,
            down_payment=10000,
            loan_interest_rate=0,
            loan_term_months=60,
            model="Ram 2500",
        )
        assert result["qualifies"] is True
        assert result["financing"] is not None
        fin = result["financing"]
        assert fin["total_interest"] == 0
        assert fin["monthly_payment"] == pytest.approx(833.33, abs=1)

    def test_gvwr_override(self):
        """Manual GVWR overrides model lookup."""
        result = calculate_section_179(
            vehicle_price=50000,
            business_use_pct=100,
            tax_bracket=37,
            gvwr_override=9500,
        )
        assert result["qualifies"] is True
        assert result["gvwr"] == 9500
        assert "manually entered" in (result["gvwr_note"] or "").lower()

    def test_unknown_model_qualifies_with_note(self):
        """Unknown model → still qualifies but with advisory note."""
        result = calculate_section_179(
            vehicle_price=50000,
            business_use_pct=100,
            tax_bracket=37,
            model="Some Unknown Truck",
        )
        assert result["qualifies"] is True
        assert result["gvwr"] is None
        assert "not in database" in (result["gvwr_note"] or "").lower()

    def test_tacoma_gvwr_lookup(self):
        """Tacoma GVWR lookup works — some trims below 6K threshold."""
        result = calculate_section_179(
            vehicle_price=40000,
            business_use_pct=100,
            tax_bracket=37,
            model="Tacoma",
        )
        assert result["qualifies"] is True
        assert result["gvwr"] is not None

    def test_luxury_auto_cap_under_6k_gvwr(self):
        """Vehicle under 6,000 lbs GVWR → IRC §280F luxury auto cap applies."""
        result = calculate_section_179(
            vehicle_price=40000,
            business_use_pct=100,
            tax_bracket=37,
            gvwr_override=5500,
        )
        assert result["qualifies"] is True
        assert result["first_year_deduction"] == 20400  # LUXURY_AUTO_FIRST_YEAR_CAP
        assert "280F" in (result["cap_note"] or "")

    def test_gvwr_override_with_known_pickup(self):
        """GVWR override with known pickup model → is_pickup detected, no SUV cap."""
        result = calculate_section_179(
            vehicle_price=80000,
            business_use_pct=100,
            tax_bracket=37,
            model="F-250",
            gvwr_override=10000,
        )
        assert result["qualifies"] is True
        assert result["first_year_deduction"] == 80000  # Full deduction, no SUV cap
        assert "exempt" in (result["cap_note"] or "").lower()

    def test_bonus_depreciation_rate_100_pct(self):
        """Bonus depreciation should be 100% (OBBBA restoration)."""
        result = calculate_section_179(
            vehicle_price=70000,
            business_use_pct=100,
            tax_bracket=37,
            model="F-250",
        )
        assert result["bonus_depreciation_rate"] == 1.0


class TestSection179Endpoint:
    """Test the POST /section-179/calculate API endpoint."""

    def test_endpoint_returns_200(self, client):
        resp = client.post("/api/v1/section-179/calculate", json={
            "vehicle_price": 70000,
            "business_use_pct": 100,
            "tax_bracket": 37,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualifies"] is True
        assert data["first_year_deduction"] > 0

    def test_no_auth_required(self, client):
        """Works without any authentication token."""
        resp = client.post("/api/v1/section-179/calculate", json={
            "vehicle_price": 50000,
            "business_use_pct": 100,
            "tax_bracket": 24,
        })
        assert resp.status_code == 200

    def test_validation_rejects_bad_input(self, client):
        """price=0 → 422 validation error."""
        resp = client.post("/api/v1/section-179/calculate", json={
            "vehicle_price": 0,
            "business_use_pct": 100,
            "tax_bracket": 37,
        })
        assert resp.status_code == 422

    def test_validation_rejects_negative_price(self, client):
        resp = client.post("/api/v1/section-179/calculate", json={
            "vehicle_price": -1000,
            "business_use_pct": 100,
            "tax_bracket": 37,
        })
        assert resp.status_code == 422
