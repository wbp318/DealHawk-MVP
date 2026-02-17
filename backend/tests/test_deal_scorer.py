"""Tests for the deal scoring engine."""

import pytest
from datetime import date
from backend.services.deal_scorer import score_deal


class TestDealScorer:
    """Test the 5-factor deal scoring algorithm with known inputs."""

    def test_ram_2500_aged_inventory(self):
        """Ram 2500 at 318 days - extreme oversupply, should score very high."""
        result = score_deal(
            asking_price=55000,
            msrp=65000,
            make="Ram",
            model="Ram 2500",
            year=2025,
            days_on_lot=318,
            rebates_available=10000,
        )
        assert result["score"] >= 75, f"Ram 2500 at 318 days should score high, got {result['score']}"
        assert result["grade"] in ("A+", "A", "B+")
        assert result["offers"]["aggressive"] <= result["offers"]["reasonable"]
        assert result["offers"]["reasonable"] <= result["offers"]["likely"]

    def test_ram_3500_worst_seller(self):
        """Ram 3500 at 342 days supply - the slowest selling vehicle."""
        result = score_deal(
            asking_price=70000,
            msrp=80000,
            make="Ram",
            model="Ram 3500",
            year=2025,
            days_on_lot=300,
            rebates_available=7000,
        )
        assert result["score"] >= 70
        # Market supply score should be very high for Ram 3500
        assert result["breakdown"]["market_supply"]["score"] >= 85

    def test_ford_f150_moderate(self):
        """Ford F-150 at 100 days - above average but not extreme."""
        result = score_deal(
            asking_price=52000,
            msrp=55000,
            make="Ford",
            model="F-150",
            year=2025,
            days_on_lot=100,
            rebates_available=3250,
        )
        assert 40 <= result["score"] <= 85
        assert result["breakdown"]["days_on_lot"]["score"] >= 50

    def test_toyota_tundra_no_deal(self):
        """Toyota Tundra - tight supply, little leverage. Should score low."""
        result = score_deal(
            asking_price=58000,
            msrp=57000,  # Above MSRP
            make="Toyota",
            model="Tundra",
            year=2026,
            days_on_lot=15,
            rebates_available=0,
        )
        assert result["score"] < 40, f"Tundra at MSRP+ should score low, got {result['score']}"

    def test_fresh_listing_low_score(self):
        """Brand new listing at MSRP should score poorly."""
        result = score_deal(
            asking_price=65000,
            msrp=65000,
            make="Ford",
            model="F-250",
            year=2026,
            days_on_lot=5,
            rebates_available=0,
        )
        assert result["score"] < 30

    def test_below_dealer_cost_perfect(self):
        """Asking price below true dealer cost should score near perfect."""
        result = score_deal(
            asking_price=48000,
            msrp=65000,
            make="Ram",
            model="Ram 1500",
            year=2025,
            days_on_lot=200,
            rebates_available=7500,
        )
        assert result["score"] >= 80
        assert result["breakdown"]["price"]["score"] >= 90

    def test_score_range(self):
        """Score should always be 0-100."""
        result = score_deal(
            asking_price=30000,
            msrp=80000,
            make="Ram",
            model="Ram 2500",
            year=2025,
            days_on_lot=400,
            rebates_available=15000,
        )
        assert 0 <= result["score"] <= 100

    def test_offer_ordering(self):
        """Aggressive < reasonable < likely (ascending price)."""
        result = score_deal(
            asking_price=60000,
            msrp=70000,
            make="Ford",
            model="F-250",
            year=2025,
            days_on_lot=120,
            rebates_available=5000,
        )
        assert result["offers"]["aggressive"] <= result["offers"]["reasonable"]
        assert result["offers"]["reasonable"] <= result["offers"]["likely"]

    def test_pricing_included(self):
        """Score result should include pricing breakdown."""
        result = score_deal(
            asking_price=55000,
            msrp=65000,
            make="Ford",
            model="F-150",
            year=2026,
            days_on_lot=60,
        )
        pricing = result["pricing"]
        assert "msrp" in pricing
        assert "invoice_price" in pricing
        assert "holdback" in pricing
        assert "true_dealer_cost" in pricing
        assert pricing["invoice_price"] < pricing["msrp"]
        assert pricing["true_dealer_cost"] < pricing["invoice_price"]

    def test_timing_quarter_end(self):
        """Scoring at quarter-end should boost timing score."""
        result_normal = score_deal(
            asking_price=55000,
            msrp=65000,
            make="Ford",
            model="F-150",
            year=2026,
            days_on_lot=60,
            score_date=date(2026, 2, 15),
        )
        result_qend = score_deal(
            asking_price=55000,
            msrp=65000,
            make="Ford",
            model="F-150",
            year=2026,
            days_on_lot=60,
            score_date=date(2026, 3, 30),
        )
        assert result_qend["breakdown"]["timing"]["score"] > result_normal["breakdown"]["timing"]["score"]

    def test_gmc_sierra_with_rebates(self):
        """GMC Sierra 1500 with $9,350 rebate - Feb 2026 data."""
        result = score_deal(
            asking_price=52000,
            msrp=58000,
            make="GMC",
            model="Sierra 1500",
            year=2025,
            days_on_lot=90,
            rebates_available=9350,
        )
        assert result["score"] >= 55
        # Incentive score should be high with $9,350 on a $58K truck (16%)
        assert result["breakdown"]["incentives"]["score"] >= 85
