"""Tests for auth: registration, login, token refresh, /me, edge cases."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base


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

    # Patch SessionLocal at the source so get_db yields test sessions
    with patch("backend.database.db.SessionLocal", TestSession):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def registered_user(client):
    """Register a user and return the response tokens."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return resp.json()


class TestAuthRegistration:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "securepass1",
            "display_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client, registered_user):
        resp = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "anotherpass1",
        })
        assert resp.status_code == 409

    def test_register_short_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "password": "short",
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "securepass1",
        })
        assert resp.status_code == 422


class TestAuthLogin:
    def test_login_success(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "whatever123",
        })
        assert resp.status_code == 401


class TestAuthTokenRefresh:
    def test_refresh_success(self, client, registered_user):
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": registered_user["refresh_token"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_with_access_token_fails(self, client, registered_user):
        """Access tokens should not work as refresh tokens."""
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": registered_user["access_token"],
        })
        assert resp.status_code == 401

    def test_refresh_with_garbage_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "not.a.valid.token",
        })
        assert resp.status_code == 401


class TestAuthMe:
    def test_get_me_success(self, client, registered_user):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {registered_user['access_token']}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"
        assert data["is_active"] is True

    def test_get_me_no_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer invalid.token.here",
        })
        assert resp.status_code == 401


class TestExistingEndpointsUnaffected:
    """Ensure Phase 1 endpoints still work without auth."""

    def test_health_no_auth(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_score_no_auth(self, client):
        resp = client.post("/api/v1/score", json={
            "asking_price": 55000,
            "msrp": 65000,
            "make": "Ford",
            "model": "F-150",
            "year": 2025,
            "days_on_lot": 90,
        })
        assert resp.status_code == 200
        assert "score" in resp.json()
