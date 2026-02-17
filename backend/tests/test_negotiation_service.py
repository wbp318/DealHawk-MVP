"""Tests for the negotiation service: brief generation, curtailment tiers, talking points."""

import pytest
from backend.services.negotiation_service import generate_negotiation_brief


class TestNegotiationBrief:

    def test_brief_contains_all_sections(self):
        """Brief should contain dealer economics, offer targets, and talking points."""
        result = generate_negotiation_brief(
            asking_price=60000,
            msrp=70000,
            invoice_price=63000,
            holdback=2100,
            true_dealer_cost=60900,
            days_on_lot=100,
            rebates_available=5000,
            make="Ram",
            model="Ram 2500",
            year=2025,
        )
        assert "dealer_economics" in result
        assert "offer_targets" in result
        assert "talking_points" in result
        assert "rebates_available" in result

    def test_curtailment_tiers(self):
        """Curtailment should scale by days on lot: 5% (91-120), 10% (121-180), 15% (181+)."""
        invoice = 60000

        # Under 90 days: no curtailment
        r0 = generate_negotiation_brief(50000, 70000, invoice, 2100, 57900, 60, make="Ram", model="Ram 2500", year=2025)
        assert r0["dealer_economics"]["curtailment_estimate"] == 0

        # 91-120 days: 5%
        r1 = generate_negotiation_brief(50000, 70000, invoice, 2100, 57900, 100, make="Ram", model="Ram 2500", year=2025)
        assert r1["dealer_economics"]["curtailment_estimate"] == pytest.approx(invoice * 0.05)

        # 121-180 days: 10%
        r2 = generate_negotiation_brief(50000, 70000, invoice, 2100, 57900, 150, make="Ram", model="Ram 2500", year=2025)
        assert r2["dealer_economics"]["curtailment_estimate"] == pytest.approx(invoice * 0.10)

        # 181+ days: 15%
        r3 = generate_negotiation_brief(50000, 70000, invoice, 2100, 57900, 200, make="Ram", model="Ram 2500", year=2025)
        assert r3["dealer_economics"]["curtailment_estimate"] == pytest.approx(invoice * 0.15)

    def test_offer_targets_present(self):
        """Offer targets should contain aggressive, reasonable, and likely_settlement."""
        result = generate_negotiation_brief(
            asking_price=70000,
            msrp=80000,
            invoice_price=72000,
            holdback=2400,
            true_dealer_cost=69600,
            days_on_lot=120,
            make="Ford",
            model="F-250",
            year=2026,
        )
        targets = result["offer_targets"]
        assert "aggressive" in targets
        assert "reasonable" in targets
        assert "likely_settlement" in targets
        # All should be positive values
        assert targets["aggressive"] > 0
        assert targets["reasonable"] > 0
        assert targets["likely_settlement"] > 0

    def test_talking_points_include_floor_plan(self):
        """Aged inventory should generate floor plan talking point."""
        result = generate_negotiation_brief(
            asking_price=55000,
            msrp=65000,
            invoice_price=58500,
            holdback=1950,
            true_dealer_cost=56550,
            days_on_lot=100,
            make="Ram",
            model="Ram 2500",
            year=2025,
        )
        categories = [tp["category"] for tp in result["talking_points"]]
        assert "Floor Plan Costs" in categories
        assert "Curtailment Pressure" in categories

    def test_talking_points_include_rebates(self):
        """When rebates are available, a rebate talking point should be present."""
        result = generate_negotiation_brief(
            asking_price=55000,
            msrp=65000,
            invoice_price=58500,
            holdback=1950,
            true_dealer_cost=56550,
            days_on_lot=50,
            rebates_available=5000,
            make="Ford",
            model="F-150",
            year=2026,
        )
        categories = [tp["category"] for tp in result["talking_points"]]
        assert "Available Rebates" in categories
