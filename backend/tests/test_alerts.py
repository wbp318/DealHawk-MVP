"""Tests for deal alerts: CRUD, matching logic, auth requirements."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base, User


@pytest.fixture
def _db_session():
    """Create a test engine and session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return TestSession


@pytest.fixture
def client(_db_session):
    with patch("backend.database.db.SessionLocal", _db_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def auth_headers(client, _db_session):
    """Register a Pro user and return auth headers."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "alertuser@example.com",
        "password": "testpass123",
    })
    token = resp.json()["access_token"]

    # Upgrade to Pro
    db = _db_session()
    user = db.query(User).filter(User.email == "alertuser@example.com").first()
    user.subscription_tier = "pro"
    user.subscription_status = "active"
    db.commit()
    db.close()

    return {"Authorization": f"Bearer {token}"}


SAMPLE_ALERT = {
    "name": "Ram deals",
    "make": "Ram",
    "model": "Ram 2500",
    "year_min": 2024,
    "year_max": 2026,
    "price_max": 60000,
    "score_min": 75,
}


class TestAlertsCRUD:
    def test_create_alert(self, client, auth_headers):
        resp = client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Ram deals"
        assert data["make"] == "Ram"
        assert data["score_min"] == 75
        assert data["is_active"] is True

    def test_list_alerts(self, client, auth_headers):
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)
        resp = client.get("/api/v1/alerts/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_alert(self, client, auth_headers):
        create_resp = client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)
        alert_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/alerts/{alert_id}",
            json={"is_active": False, "score_min": 80},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert resp.json()["score_min"] == 80

    def test_delete_alert(self, client, auth_headers):
        create_resp = client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)
        alert_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/alerts/{alert_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        resp = client.get(f"/api/v1/alerts/{alert_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestAlertsAuth:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/alerts/")
        assert resp.status_code == 401

    def test_create_requires_auth(self, client):
        resp = client.post("/api/v1/alerts/", json=SAMPLE_ALERT)
        assert resp.status_code == 401

    def test_check_requires_auth(self, client):
        resp = client.post("/api/v1/alerts/check", json={"make": "Ram"})
        assert resp.status_code == 401


class TestAlertMatching:
    def test_matching_listing(self, client, auth_headers):
        """A Ram 2500 with score 85 and price $55K should match the alert."""
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)

        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 85,
            "days_on_lot": 120,
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["matches"][0]["name"] == "Ram deals"

    def test_non_matching_make(self, client, auth_headers):
        """A Ford F-150 should NOT match a Ram alert."""
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)

        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ford",
            "model": "F-150",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 85,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_non_matching_score(self, client, auth_headers):
        """A Ram 2500 with score 50 should NOT match (min score 75)."""
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)

        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 50,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_non_matching_price(self, client, auth_headers):
        """A Ram 2500 at $70K should NOT match (max price $60K)."""
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)

        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "asking_price": 70000,
            "deal_score": 85,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_inactive_alert_not_matched(self, client, auth_headers):
        """Deactivated alerts should not match."""
        create_resp = client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)
        alert_id = create_resp.json()["id"]

        # Deactivate the alert
        client.patch(f"/api/v1/alerts/{alert_id}", json={"is_active": False}, headers=auth_headers)

        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 85,
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_days_on_lot_min_filter(self, client, auth_headers):
        """Alert with days_on_lot_min should filter listings below that threshold."""
        alert_data = {
            "name": "Aged inventory only",
            "make": "Ram",
            "days_on_lot_min": 90,
        }
        client.post("/api/v1/alerts/", json=alert_data, headers=auth_headers)

        # 30 days should NOT match
        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 85,
            "days_on_lot": 30,
        }, headers=auth_headers)
        assert resp.json()["count"] == 0

        # 120 days SHOULD match
        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 85,
            "days_on_lot": 120,
        }, headers=auth_headers)
        assert resp.json()["count"] == 1

    def test_model_substring_match(self, client, auth_headers):
        """Alert model uses substring matching (e.g., 'Ram 2500' matches 'Ram 2500 Laramie')."""
        alert_data = {
            "name": "Ram 2500 deals",
            "make": "Ram",
            "model": "Ram 2500",
        }
        client.post("/api/v1/alerts/", json=alert_data, headers=auth_headers)

        # Listing model "Ram 2500 Laramie" contains alert model "Ram 2500" — should match
        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500 Laramie",
            "year": 2025,
            "asking_price": 55000,
            "deal_score": 75,
        }, headers=auth_headers)
        assert resp.json()["count"] == 1

    def test_year_range_boundary(self, client, auth_headers):
        """Year exactly at min/max boundary should match; outside should not."""
        # SAMPLE_ALERT has year_min=2024, year_max=2026
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)

        # 2024 (at min) should match
        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram", "model": "Ram 2500", "year": 2024,
            "asking_price": 55000, "deal_score": 85,
        }, headers=auth_headers)
        assert resp.json()["count"] == 1

        # 2023 (below min) should NOT match
        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram", "model": "Ram 2500", "year": 2023,
            "asking_price": 55000, "deal_score": 85,
        }, headers=auth_headers)
        assert resp.json()["count"] == 0

    def test_missing_listing_data_does_not_match(self, client, auth_headers):
        """When alert sets a criterion but listing lacks that data, should NOT match."""
        client.post("/api/v1/alerts/", json=SAMPLE_ALERT, headers=auth_headers)

        # Listing with no year — SAMPLE_ALERT has year_min=2024
        resp = client.post("/api/v1/alerts/check", json={
            "make": "Ram",
            "model": "Ram 2500",
            "asking_price": 55000,
            "deal_score": 85,
        }, headers=auth_headers)
        # year is missing (None) so year_min check fails → no match
        assert resp.json()["count"] == 0
