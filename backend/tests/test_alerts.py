"""Tests for deal alerts: CRUD, matching logic, auth requirements."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base


@pytest.fixture
def client():
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


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/v1/auth/register", json={
        "email": "alertuser@example.com",
        "password": "testpass123",
    })
    token = resp.json()["access_token"]
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
