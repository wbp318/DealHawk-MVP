"""Tests for saved vehicles CRUD, auth requirements, and user isolation."""

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
    """Register a user and return auth headers."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "user1@example.com",
        "password": "testpass123",
        "display_name": "User One",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user2(client):
    """Register a second user and return auth headers."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "user2@example.com",
        "password": "testpass456",
        "display_name": "User Two",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


SAMPLE_VEHICLE = {
    "vin": "1C6SRFFT5PN123456",
    "platform": "cargurus",
    "listing_url": "https://www.cargurus.com/listing/123",
    "asking_price": 55000,
    "msrp": 65000,
    "year": 2025,
    "make": "Ram",
    "model": "Ram 2500",
    "trim": "Laramie",
    "days_on_lot": 120,
    "dealer_name": "Test Dealer",
    "dealer_location": "Atlanta, GA",
    "deal_score": 82,
    "deal_grade": "A",
    "notes": "Great deal on aged inventory",
}


class TestSavedVehiclesCRUD:
    def test_save_vehicle(self, client, auth_headers):
        resp = client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["vin"] == "1C6SRFFT5PN123456"
        assert data["make"] == "Ram"
        assert data["deal_score"] == 82
        assert data["id"] is not None

    def test_list_saved(self, client, auth_headers):
        client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)
        resp = client.get("/api/v1/saved/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["make"] == "Ram"

    def test_get_saved_by_id(self, client, auth_headers):
        create_resp = client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)
        vehicle_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/saved/{vehicle_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["vin"] == "1C6SRFFT5PN123456"

    def test_update_saved(self, client, auth_headers):
        create_resp = client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)
        vehicle_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/saved/{vehicle_id}",
            json={"notes": "Updated notes", "deal_score": 90},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated notes"
        assert resp.json()["deal_score"] == 90

    def test_delete_saved(self, client, auth_headers):
        create_resp = client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)
        vehicle_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/saved/{vehicle_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify it's gone
        resp = client.get(f"/api/v1/saved/{vehicle_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestSavedVehiclesAuth:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/v1/saved/")
        assert resp.status_code == 401

    def test_save_requires_auth(self, client):
        resp = client.post("/api/v1/saved/", json=SAMPLE_VEHICLE)
        assert resp.status_code == 401

    def test_delete_requires_auth(self, client):
        resp = client.delete("/api/v1/saved/1")
        assert resp.status_code == 401


class TestSavedVehiclesUserIsolation:
    def test_user_cannot_see_other_users_vehicles(self, client, auth_headers, auth_headers_user2):
        # User 1 saves a vehicle
        client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)

        # User 2 should see empty list
        resp = client.get("/api/v1/saved/", headers=auth_headers_user2)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_user_cannot_delete_other_users_vehicles(self, client, auth_headers, auth_headers_user2):
        create_resp = client.post("/api/v1/saved/", json=SAMPLE_VEHICLE, headers=auth_headers)
        vehicle_id = create_resp.json()["id"]

        # User 2 tries to delete User 1's vehicle
        resp = client.delete(f"/api/v1/saved/{vehicle_id}", headers=auth_headers_user2)
        assert resp.status_code == 404
