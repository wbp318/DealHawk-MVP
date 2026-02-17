"""Tests for Dealer API tier — auth, rate limiting, bulk scoring, inventory analysis."""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base, Dealership, IncentiveProgram
from backend.api.dealer_auth import _hash_api_key


TEST_API_KEY = "dh_dealer_test_key_12345678901234567890"


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
def client_with_dealer(test_session):
    """Client with an active dealer in the database."""
    db = test_session()
    dealer = Dealership(
        name="Test Dealer",
        email="test@dealer.com",
        api_key_hash=_hash_api_key(TEST_API_KEY),
        is_active=True,
        tier="standard",
        daily_rate_limit=1000,
        monthly_rate_limit=25000,
        requests_today=0,
        requests_this_month=0,
    )
    db.add(dealer)
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def client_with_seeded_dealer(test_session):
    """Client with dealer + seeded incentive data."""
    db = test_session()
    dealer = Dealership(
        name="Seeded Dealer",
        email="seeded@dealer.com",
        api_key_hash=_hash_api_key(TEST_API_KEY),
        is_active=True,
        tier="standard",
        daily_rate_limit=1000,
        monthly_rate_limit=25000,
        requests_today=0,
        requests_this_month=0,
    )
    db.add(dealer)
    db.add(IncentiveProgram(
        make="Ram", model="Ram 2500", year=2026,
        incentive_type="cash_back", name="Test Cash Back",
        amount=7000, region="national",
        start_date=date(2026, 2, 1), end_date=date(2026, 3, 31),
    ))
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def client_no_dealer(test_session):
    """Client with no dealers in DB."""
    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


def _auth_headers():
    return {"X-API-Key": TEST_API_KEY}


class TestDealerAuth:

    def test_valid_api_key(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

    def test_missing_api_key(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]},
        )
        assert resp.status_code == 401

    def test_invalid_api_key(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]},
            headers={"X-API-Key": "dh_dealer_wrong_key"},
        )
        assert resp.status_code == 401

    def test_inactive_dealer_rejected(self, test_session):
        """is_active=False → 401."""
        db = test_session()
        dealer = Dealership(
            name="Inactive Dealer",
            email="inactive@dealer.com",
            api_key_hash=_hash_api_key("dh_dealer_inactive_key"),
            is_active=False,
            tier="standard",
            daily_rate_limit=1000,
            monthly_rate_limit=25000,
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            app = create_app()
            client = TestClient(app)
            resp = client.post(
                "/api/v1/dealer/score/bulk",
                json={"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]},
                headers={"X-API-Key": "dh_dealer_inactive_key"},
            )
            assert resp.status_code == 401


class TestDealerRateLimiting:

    def test_daily_limit_enforced(self, test_session):
        """429 after exceeding daily limit."""
        db = test_session()
        dealer = Dealership(
            name="Limited Dealer",
            email="limited@dealer.com",
            api_key_hash=_hash_api_key("dh_dealer_limited"),
            is_active=True,
            daily_rate_limit=2,
            monthly_rate_limit=25000,
            requests_today=0,
            requests_this_month=0,
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            app = create_app()
            client = TestClient(app)
            headers = {"X-API-Key": "dh_dealer_limited"}
            body = {"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]}

            # First two should succeed
            assert client.post("/api/v1/dealer/score/bulk", json=body, headers=headers).status_code == 200
            assert client.post("/api/v1/dealer/score/bulk", json=body, headers=headers).status_code == 200
            # Third should be rate limited
            resp = client.post("/api/v1/dealer/score/bulk", json=body, headers=headers)
            assert resp.status_code == 429

    def test_monthly_limit_enforced(self, test_session):
        """429 after exceeding monthly limit."""
        db = test_session()
        dealer = Dealership(
            name="Monthly Limited",
            email="monthly@dealer.com",
            api_key_hash=_hash_api_key("dh_dealer_monthly"),
            is_active=True,
            daily_rate_limit=1000,
            monthly_rate_limit=1,
            requests_today=0,
            requests_this_month=0,
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            app = create_app()
            client = TestClient(app)
            headers = {"X-API-Key": "dh_dealer_monthly"}
            body = {"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]}

            assert client.post("/api/v1/dealer/score/bulk", json=body, headers=headers).status_code == 200
            resp = client.post("/api/v1/dealer/score/bulk", json=body, headers=headers)
            assert resp.status_code == 429

    def test_429_includes_retry_after(self, test_session):
        """Rate limit response includes Retry-After header."""
        db = test_session()
        dealer = Dealership(
            name="Retry Dealer",
            email="retry@dealer.com",
            api_key_hash=_hash_api_key("dh_dealer_retry"),
            is_active=True,
            daily_rate_limit=1,
            monthly_rate_limit=25000,
            requests_today=0,
            requests_this_month=0,
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            app = create_app()
            client = TestClient(app)
            headers = {"X-API-Key": "dh_dealer_retry"}
            body = {"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]}

            client.post("/api/v1/dealer/score/bulk", json=body, headers=headers)
            resp = client.post("/api/v1/dealer/score/bulk", json=body, headers=headers)
            assert resp.status_code == 429
            assert "retry-after" in resp.headers


class TestBulkScoring:

    def test_bulk_score_success(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": [
                {"asking_price": 55000, "msrp": 65000, "make": "Ram", "model": "Ram 2500", "year": 2026, "days_on_lot": 100}
            ]},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["results"][0]["score"] >= 0

    def test_bulk_score_multiple(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": [
                {"asking_price": 55000, "msrp": 65000, "make": "Ram", "model": "Ram 2500", "year": 2026},
                {"asking_price": 45000, "msrp": 55000, "make": "Ford", "model": "F-150", "year": 2026},
                {"asking_price": 60000, "msrp": 70000, "make": "GMC", "model": "Sierra 1500", "year": 2025},
            ]},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

    def test_bulk_score_max_50(self, client_with_dealer):
        """51 vehicles → 422 validation error."""
        vehicles = [
            {"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}
        ] * 51
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": vehicles},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_bulk_score_empty(self, client_with_dealer):
        """Empty vehicles list → 422."""
        resp = client_with_dealer.post(
            "/api/v1/dealer/score/bulk",
            json={"vehicles": []},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422


class TestDealerMarketAndIncentives:

    def test_dealer_market_trends(self, client_with_dealer):
        resp = client_with_dealer.get(
            "/api/v1/dealer/market/Ram/Ram%202500",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["days_supply"] == 318

    def test_dealer_incentives(self, client_with_seeded_dealer):
        resp = client_with_seeded_dealer.get(
            "/api/v1/dealer/incentives/Ram",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["make"] == "Ram"

    def test_incentives_model_filter(self, client_with_seeded_dealer):
        resp = client_with_seeded_dealer.get(
            "/api/v1/dealer/incentives/Ram?model=Ram%202500",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["model"] == "Ram 2500" for i in data)


class TestInventoryAnalysis:

    def test_inventory_analysis(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/inventory/analysis",
            json={"vehicles": [
                {"vin": "1C6SRFFT1NN123456", "make": "Ram", "model": "Ram 2500", "year": 2026, "days_on_lot": 120, "asking_price": 65000, "msrp": 70000},
                {"vin": "1FTFW1E50NFA12345", "make": "Ford", "model": "F-150", "year": 2026, "days_on_lot": 30, "asking_price": 50000, "msrp": 55000},
            ]},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_vehicles"] == 2
        assert data["summary"]["aged_count"] == 1  # Only the Ram at 120 days
        assert len(data["vehicles"]) == 2

    def test_aged_inventory_detection(self, client_with_dealer):
        resp = client_with_dealer.post(
            "/api/v1/dealer/inventory/analysis",
            json={"vehicles": [
                {"make": "Ram", "model": "Ram 3500", "year": 2025, "days_on_lot": 200},
            ]},
            headers=_auth_headers(),
        )
        data = resp.json()
        assert data["summary"]["aged_count"] == 1
        assert data["vehicles"][0]["risk_tier"] == "critical"

    def test_carrying_cost_calculation(self, client_with_dealer):
        """days * $7.90."""
        resp = client_with_dealer.post(
            "/api/v1/dealer/inventory/analysis",
            json={"vehicles": [
                {"make": "Ford", "model": "F-250", "year": 2026, "days_on_lot": 100},
            ]},
            headers=_auth_headers(),
        )
        data = resp.json()
        assert data["vehicles"][0]["carrying_cost"] == pytest.approx(790.0)

    def test_risk_tier_assignment(self, client_with_dealer):
        """Correct risk tiers at day thresholds."""
        resp = client_with_dealer.post(
            "/api/v1/dealer/inventory/analysis",
            json={"vehicles": [
                {"make": "Ford", "model": "F-150", "year": 2026, "days_on_lot": 30},
                {"make": "Ford", "model": "F-150", "year": 2026, "days_on_lot": 65},
                {"make": "Ford", "model": "F-150", "year": 2026, "days_on_lot": 95},
                {"make": "Ford", "model": "F-150", "year": 2026, "days_on_lot": 200},
            ]},
            headers=_auth_headers(),
        )
        tiers = [v["risk_tier"] for v in resp.json()["vehicles"]]
        assert tiers == ["low", "moderate", "high", "critical"]


class TestConsumerEndpointsUnaffected:

    def test_consumer_score_works_without_api_key(self, client_no_dealer):
        """POST /score still works without X-API-Key header."""
        resp = client_no_dealer.post("/api/v1/score", json={
            "asking_price": 55000,
            "msrp": 65000,
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2026,
        })
        assert resp.status_code == 200
        assert "score" in resp.json()


class TestRateLimitReset:

    def test_daily_counter_reset_on_new_day(self, test_session):
        """Daily counter should reset when a new day arrives."""
        from datetime import date, timedelta

        db = test_session()
        yesterday = date.today() - timedelta(days=1)
        dealer = Dealership(
            name="Reset Daily Dealer",
            email="daily_reset@dealer.com",
            api_key_hash=_hash_api_key("dh_dealer_daily_reset"),
            is_active=True,
            daily_rate_limit=5,
            monthly_rate_limit=25000,
            requests_today=4,  # Near limit from yesterday
            requests_this_month=10,
            last_request_date=yesterday,
            last_request_month=yesterday.strftime("%Y-%m"),
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            app = create_app()
            client = TestClient(app)

            # Should succeed because it's a new day — counter resets
            resp = client.post(
                "/api/v1/dealer/score/bulk",
                json={"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]},
                headers={"X-API-Key": "dh_dealer_daily_reset"},
            )
            assert resp.status_code == 200

    def test_monthly_counter_reset_on_new_month(self, test_session):
        """Monthly counter should reset when a new month arrives."""
        db = test_session()
        dealer = Dealership(
            name="Reset Monthly Dealer",
            email="monthly_reset@dealer.com",
            api_key_hash=_hash_api_key("dh_dealer_monthly_reset"),
            is_active=True,
            daily_rate_limit=1000,
            monthly_rate_limit=5,
            requests_today=0,
            requests_this_month=4,  # Near limit from last month
            last_request_date=date(2025, 12, 15),
            last_request_month="2025-12",
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            app = create_app()
            client = TestClient(app)

            # Should succeed because it's a new month — counter resets
            resp = client.post(
                "/api/v1/dealer/score/bulk",
                json={"vehicles": [{"asking_price": 50000, "msrp": 60000, "make": "Ford", "model": "F-150", "year": 2026}]},
                headers={"X-API-Key": "dh_dealer_monthly_reset"},
            )
            assert resp.status_code == 200


class TestProductionValidation:

    def test_validate_production_dealer_salt(self):
        """Default dealer salt should be blocked in production."""
        from backend.config.settings import Settings
        s = Settings(
            environment="production",
            jwt_secret_key="prod-safe-secret-key",
            stripe_secret_key="sk_live_test",
            stripe_webhook_secret="whsec_test",
            stripe_pro_price_id="price_test",
            base_url="https://api.dealhawk.app",
            dealer_api_key_salt="dealhawk-dealer-key-salt",
        )
        with pytest.raises(ValueError, match="DEALER_API_KEY_SALT"):
            s.validate_production()
