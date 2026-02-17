"""Tests for the billing portal endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

from backend.database.models import Base, User


@pytest.fixture
def _db_session():
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


def _register(client, email="portal@example.com"):
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


class TestPortalEndpoint:

    @patch("backend.services.stripe_service._get_stripe")
    def test_portal_success(self, mock_get_stripe, client, _db_session):
        """Pro user with stripe_customer_id can access billing portal."""
        token = _register(client)
        db = _db_session()
        user = db.query(User).filter(User.email == "portal@example.com").first()
        user.subscription_tier = "pro"
        user.subscription_status = "active"
        user.stripe_customer_id = "cus_portal_test"
        db.commit()
        db.close()

        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.billing_portal.Session.create.return_value = MagicMock(
            url="https://billing.stripe.com/session/test"
        )

        resp = client.post("/subscription/portal", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "portal_url" in resp.json()
        assert "stripe.com" in resp.json()["portal_url"]

    def test_portal_requires_auth(self, client):
        """Portal endpoint requires authentication."""
        resp = client.post("/subscription/portal")
        assert resp.status_code == 401

    def test_portal_no_billing_account(self, client, _db_session):
        """User without stripe_customer_id should get 400."""
        token = _register(client)
        resp = client.post("/subscription/portal", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400
        assert "No billing account" in resp.json()["detail"]

    @patch("backend.services.stripe_service._get_stripe")
    def test_portal_stripe_failure(self, mock_get_stripe, client, _db_session):
        """Stripe failure should return 502, not expose internals."""
        token = _register(client)
        db = _db_session()
        user = db.query(User).filter(User.email == "portal@example.com").first()
        user.stripe_customer_id = "cus_portal_fail"
        db.commit()
        db.close()

        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.billing_portal.Session.create.side_effect = Exception("Stripe API error")

        resp = client.post("/subscription/portal", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 502
        assert "Stripe API error" not in resp.json()["detail"]
