"""Tests for dealer dashboard — login, session auth, pages."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from backend.database.models import Base, Dealership
from backend.api.dealer_auth import _hash_api_key
from backend.services.auth_service import hash_password


TEST_API_KEY = "dh_dealer_test_dashboard_1234567890"
TEST_PASSWORD = "testpass123"


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
    db = test_session()
    dealer = Dealership(
        name="Dashboard Dealer",
        email="dash@dealer.com",
        api_key_hash=_hash_api_key(TEST_API_KEY),
        hashed_password=hash_password(TEST_PASSWORD),
        is_active=True,
        tier="standard",
        daily_rate_limit=1000,
        monthly_rate_limit=25000,
        requests_today=5,
        requests_this_month=150,
    )
    db.add(dealer)
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


class TestDealerDashboard:

    def test_login_page_renders(self, client_with_dealer):
        response = client_with_dealer.get("/dashboard/login")
        assert response.status_code == 200
        assert "DealHawk" in response.text
        assert "Sign In" in response.text

    def test_login_success_sets_cookie(self, client_with_dealer):
        response = client_with_dealer.post(
            "/dashboard/login",
            data={"email": "dash@dealer.com", "password": TEST_PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"
        assert "dh_dealer_session" in response.cookies

    def test_login_wrong_password_returns_401(self, client_with_dealer):
        response = client_with_dealer.post(
            "/dashboard/login",
            data={"email": "dash@dealer.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.text

    def test_login_nonexistent_email_returns_401(self, client_with_dealer):
        response = client_with_dealer.post(
            "/dashboard/login",
            data={"email": "nobody@dealer.com", "password": TEST_PASSWORD},
        )
        assert response.status_code == 401

    def test_dashboard_requires_login(self, client_with_dealer):
        response = client_with_dealer.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/dashboard/login" in response.headers["location"]

    def test_dashboard_renders_with_session(self, client_with_dealer):
        # Login first
        login_resp = client_with_dealer.post(
            "/dashboard/login",
            data={"email": "dash@dealer.com", "password": TEST_PASSWORD},
            follow_redirects=False,
        )
        cookies = login_resp.cookies

        # Access dashboard with session cookie
        response = client_with_dealer.get("/dashboard", cookies=cookies)
        assert response.status_code == 200
        assert "Dashboard Dealer" in response.text

    def test_logout_clears_cookie(self, client_with_dealer):
        # Login first
        login_resp = client_with_dealer.post(
            "/dashboard/login",
            data={"email": "dash@dealer.com", "password": TEST_PASSWORD},
            follow_redirects=False,
        )
        cookies = login_resp.cookies

        # Logout
        response = client_with_dealer.get("/dashboard/logout", cookies=cookies, follow_redirects=False)
        assert response.status_code == 303
        assert "/dashboard/login" in response.headers["location"]

    def test_inventory_page_requires_login(self, client_with_dealer):
        response = client_with_dealer.get("/dashboard/inventory", follow_redirects=False)
        assert response.status_code == 303

    def test_market_page_requires_login(self, client_with_dealer):
        response = client_with_dealer.get("/dashboard/market", follow_redirects=False)
        assert response.status_code == 303
