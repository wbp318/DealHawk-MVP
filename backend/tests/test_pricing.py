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
