"""Tests for MarketCheck service (stub mode) and market endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base
from backend.database.db import get_db


@pytest.fixture
def test_session():
    """Create isolated in-memory SQLite DB and return session factory."""
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
    """Create a test client with isolated DB."""
    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def seeded_client(test_session):
    """Client with seeded incentive data for realistic trend tests."""
    from backend.database.models import IncentiveProgram
    from datetime import date

    db = test_session()
    db.add(IncentiveProgram(
        make="Ram", model="Ram 2500", year=2026,
        incentive_type="cash_back", name="Ram 2500 Cash",
        amount=7000, region="national",
        start_date=date(2026, 2, 1), end_date=date(2026, 3, 31),
    ))
    db.add(IncentiveProgram(
        make="Ram", model="Ram 2500", year=2025,
        incentive_type="cash_back", name="2025 Ram 2500 Cash",
        amount=10000, region="national",
        start_date=date(2026, 2, 1), end_date=date(2026, 3, 31),
    ))
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


class TestStubTrends:
    """Test stub trend data from existing MODEL_DAYS_SUPPLY."""

    def test_stub_trends_ram_2500(self, seeded_client):
        resp = seeded_client.get("/api/v1/market/trends/Ram/Ram%202500")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_supply"] == 318
        assert data["supply_level"] == "oversupplied"
        assert data["price_trend"] == "declining"
        assert data["source"] == "stub"
        assert data["active_incentive_count"] == 2
        assert data["total_incentive_value"] == 17000

    def test_stub_trends_tundra(self, client):
        resp = client.get("/api/v1/market/trends/Toyota/Tundra")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_supply"] == 33
        assert data["supply_level"] == "undersupplied"
        assert data["price_trend"] == "rising"

    def test_stub_trends_unknown_model(self, client):
        resp = client.get("/api/v1/market/trends/Generic/Unknown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days_supply"] == 76  # Falls back to industry avg
        assert data["supply_level"] == "balanced"


class TestStubStats:

    def test_stub_stats_returns_data(self, client):
        resp = client.get("/api/v1/market/stats/Ford/F-150")
        assert resp.status_code == 200
        data = resp.json()
        assert "avg_price" in data
        assert "price_range_low" in data
        assert "price_range_high" in data
        assert "median_days_on_lot" in data
        assert data["source"] == "stub"


class TestMarketCache:

    def test_cache_stores_response(self, test_session):
        """After fetching trends, a cache entry should exist."""
        from backend.services.marketcheck_service import get_market_trends
        from backend.database.models import MarketDataCache

        db = test_session()
        get_market_trends("Ford", "F-150", db)

        cached = db.query(MarketDataCache).filter(
            MarketDataCache.cache_key == "trends:Ford:F-150"
        ).first()
        assert cached is not None
        assert "days_supply" in cached.response_json
        db.close()

    def test_cache_hit_returns_cached(self, test_session):
        """Second call uses cache (same data returned)."""
        from backend.services.marketcheck_service import get_market_trends

        db = test_session()
        result1 = get_market_trends("Ram", "Ram 3500", db)
        result2 = get_market_trends("Ram", "Ram 3500", db)
        # Same data
        assert result1["days_supply"] == result2["days_supply"]
        assert result1["supply_level"] == result2["supply_level"]
        db.close()


class TestMarketEndpoints:

    def test_trends_endpoint(self, client):
        resp = client.get("/api/v1/market/trends/Ram/Ram%202500")
        assert resp.status_code == 200

    def test_stats_endpoint(self, client):
        resp = client.get("/api/v1/market/stats/Ford/F-150")
        assert resp.status_code == 200

    def test_no_auth_required(self, client):
        """Market endpoints work without any auth token."""
        resp = client.get("/api/v1/market/trends/Ford/F-150")
        assert resp.status_code == 200

    def test_trends_response_fields(self, client):
        resp = client.get("/api/v1/market/trends/Ford/F-150")
        data = resp.json()
        required_fields = [
            "make", "model", "days_supply", "industry_avg_days_supply",
            "supply_ratio", "supply_level", "price_trend",
            "active_incentive_count", "total_incentive_value",
            "inventory_level", "source", "as_of",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_stats_response_fields(self, client):
        resp = client.get("/api/v1/market/stats/Ford/F-150")
        data = resp.json()
        required_fields = [
            "make", "model", "avg_price", "price_range_low",
            "price_range_high", "median_days_on_lot",
            "total_active_listings", "source", "as_of",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_url_encoded_model(self, client):
        """Spaces in model name work correctly."""
        resp = client.get("/api/v1/market/trends/Ram/Ram%202500")
        assert resp.status_code == 200
        assert resp.json()["model"] == "Ram 2500"


class TestMarketErrorHandling:

    @patch("backend.api.market_routes.get_market_trends")
    def test_trends_502_on_exception(self, mock_trends, client):
        """Market trends endpoint should return 502 on service exception."""
        mock_trends.side_effect = RuntimeError("DB connection lost")
        resp = client.get("/api/v1/market/trends/Ford/F-150")
        assert resp.status_code == 502
        assert "temporarily unavailable" in resp.json()["detail"].lower()
        # Should NOT expose the raw error
        assert "DB connection" not in resp.json()["detail"]

    @patch("backend.api.market_routes.get_market_stats")
    def test_stats_502_on_exception(self, mock_stats, client):
        """Market stats endpoint should return 502 on service exception."""
        mock_stats.side_effect = RuntimeError("Timeout")
        resp = client.get("/api/v1/market/stats/Ford/F-150")
        assert resp.status_code == 502
        assert "temporarily unavailable" in resp.json()["detail"].lower()


class TestMarketCacheUpdate:

    def test_cache_update_existing_entry(self, test_session):
        """Storing cache for a key that already exists should update, not duplicate."""
        from backend.services.marketcheck_service import get_market_trends
        from backend.database.models import MarketDataCache
        from datetime import datetime, timedelta

        db = test_session()

        # First call creates cache entry
        get_market_trends("Ram", "Ram 2500", db)
        count1 = db.query(MarketDataCache).filter(
            MarketDataCache.cache_key == "trends:Ram:Ram 2500"
        ).count()
        assert count1 == 1

        # Expire the existing cache to force re-fetch
        entry = db.query(MarketDataCache).filter(
            MarketDataCache.cache_key == "trends:Ram:Ram 2500"
        ).first()
        entry.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()

        # Second call should update the existing entry, not create a new one
        get_market_trends("Ram", "Ram 2500", db)
        count2 = db.query(MarketDataCache).filter(
            MarketDataCache.cache_key == "trends:Ram:Ram 2500"
        ).count()
        assert count2 == 1  # Still just one entry, not two
        db.close()
