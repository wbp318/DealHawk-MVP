"""Tests for the pricing service."""

import pytest
from backend.services.pricing_service import get_pricing
from backend.config.holdback_rates import get_holdback
from backend.config.invoice_ranges import estimate_invoice


class TestPricingService:
    """Test invoice calculation and true dealer cost computation."""

    def test_ford_f150_pricing(self):
        """F-150 at $55K MSRP should produce reasonable invoice estimate."""
        result = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000)
        # Invoice should be ~91% of MSRP for mid-trim F-150
        assert 48000 < result["invoice_price"] < 52000
        assert result["holdback"] > 0
        assert result["true_dealer_cost"] < result["invoice_price"]
        assert result["source"] == "estimated"

    def test_ram_2500_pricing(self):
        """Ram 2500 at $65K MSRP."""
        result = get_pricing(year=2025, make="Ram", model="Ram 2500", msrp=65000)
        assert 57000 < result["invoice_price"] < 61000
        # Ram holdback is 3% of MSRP
        assert abs(result["holdback"] - 1950) < 1

    def test_dealer_cash_reduces_cost(self):
        """Dealer cash should reduce true dealer cost."""
        result_no_cash = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000)
        result_with_cash = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000, dealer_cash=2000)
        assert result_with_cash["true_dealer_cost"] == result_no_cash["true_dealer_cost"] - 2000

    def test_margin_calculation(self):
        """Margin from MSRP should be MSRP minus true cost."""
        result = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000)
        expected_margin = 55000 - result["true_dealer_cost"]
        assert abs(result["margin_from_msrp"] - expected_margin) < 1

    def test_margin_percentage(self):
        """Margin percentage should be reasonable (8-15% for trucks)."""
        result = get_pricing(year=2026, make="Ram", model="Ram 1500", msrp=50000)
        assert 8 < result["margin_pct"] < 16


class TestHoldbackRates:
    """Test holdback calculation."""

    def test_ram_holdback_on_msrp(self):
        """Ram holdback is 3% of MSRP."""
        holdback = get_holdback("Ram", msrp=65000, invoice=59800)
        assert holdback == 1950.0

    def test_chevy_holdback_on_invoice(self):
        """Chevrolet holdback is 3% of invoice."""
        holdback = get_holdback("Chevrolet", msrp=55000, invoice=50600)
        assert holdback == 1518.0

    def test_ford_holdback_on_msrp(self):
        """Ford holdback is 3% of MSRP."""
        holdback = get_holdback("Ford", msrp=55000, invoice=50050)
        assert holdback == 1650.0

    def test_unknown_make_defaults(self):
        """Unknown make should use 2% of MSRP default."""
        holdback = get_holdback("UnknownMake", msrp=50000, invoice=45000)
        assert holdback == 1000.0


class TestInvoiceEstimation:
    """Test invoice-to-MSRP ratio estimation."""

    def test_f150_base_trim(self):
        """F-150 base trim (under $42K) should use base ratio (93%)."""
        invoice = estimate_invoice("Ford", "F-150", 40000)
        assert invoice == 37200.0  # 40000 * 0.93

    def test_f150_high_trim(self):
        """F-150 high trim (over $65K) should use high ratio (89%)."""
        invoice = estimate_invoice("Ford", "F-150", 75000)
        assert invoice == 66750.0  # 75000 * 0.89

    def test_ram_2500_mid_trim(self):
        """Ram 2500 mid trim should use mid ratio (90%)."""
        invoice = estimate_invoice("Ram", "Ram 2500", 60000)
        assert invoice == 54000.0  # 60000 * 0.90

    def test_unknown_vehicle_uses_default(self):
        """Unknown vehicle should use 92% default."""
        invoice = estimate_invoice("UnknownMake", "UnknownModel", 50000)
        assert invoice == 46000.0  # 50000 * 0.92


class TestPricingDBCache:
    """Test the DB cache path in get_pricing()."""

    def test_cached_invoice_price(self):
        """When DB has a cached invoice price, it should be used instead of estimation."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from backend.database.models import Base, InvoicePriceCache

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        # Seed a cached invoice price
        db.add(InvoicePriceCache(
            year=2026, make="Ford", model="F-150", msrp=55000,
            invoice_price=49500, holdback_amount=1650,
        ))
        db.commit()

        result = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000, db=db)
        assert result["invoice_price"] == 49500
        assert result["holdback"] == 1650
        assert result["source"] == "cached"
        db.close()

    def test_cache_overrides_estimation(self):
        """Cached values should differ from estimated values."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from backend.database.models import Base, InvoicePriceCache

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        # Get estimated result (no cache)
        estimated = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000, db=db)
        assert estimated["source"] == "estimated"

        # Add cache entry with different values
        db.add(InvoicePriceCache(
            year=2026, make="Ford", model="F-150", msrp=55000,
            invoice_price=48000, holdback_amount=1700,
        ))
        db.commit()

        cached = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000, db=db)
        assert cached["source"] == "cached"
        assert cached["invoice_price"] == 48000
        assert cached["invoice_price"] != estimated["invoice_price"]
        db.close()

    def test_cache_miss_falls_back_to_estimation(self):
        """When DB has no cache entry, should fall back to estimation."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from backend.database.models import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()

        result = get_pricing(year=2026, make="Ford", model="F-150", msrp=55000, db=db)
        assert result["source"] == "estimated"
        db.close()
