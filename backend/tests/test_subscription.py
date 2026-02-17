"""Tests for subscription tier enforcement, Stripe integration, and webhook handling."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

from backend.database.models import Base, User, ProcessedWebhookEvent


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


def _register(client, email="sub@example.com", password="testpass123"):
    """Register a user and return token."""
    resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _upgrade_to_pro(db_session, email):
    """Upgrade a user to Pro in the DB."""
    db = db_session()
    user = db.query(User).filter(User.email == email).first()
    user.subscription_tier = "pro"
    user.subscription_status = "active"
    user.stripe_customer_id = "cus_test123"
    user.subscription_stripe_id = "sub_test123"
    db.commit()
    db.close()


def _set_past_due(db_session, email):
    """Set a Pro user's subscription to past_due."""
    db = db_session()
    user = db.query(User).filter(User.email == email).first()
    user.subscription_tier = "pro"
    user.subscription_status = "past_due"
    user.stripe_customer_id = "cus_test123"
    db.commit()
    db.close()


class TestSubscriptionStatus:
    def test_status_free_user(self, client, _db_session):
        token = _register(client)
        resp = client.get("/subscription/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["status"] == "active"
        # stripe_subscription_id should NOT be in response (security: don't leak Stripe IDs)
        assert "stripe_subscription_id" not in data

    def test_status_pro_user(self, client, _db_session):
        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")
        resp = client.get("/subscription/status", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "pro"
        assert data["status"] == "active"

    def test_status_requires_auth(self, client):
        resp = client.get("/subscription/status")
        assert resp.status_code == 401


class TestTierEnforcement:
    def test_free_user_cannot_save_vehicle(self, client, _db_session):
        token = _register(client)
        resp = client.get("/api/v1/saved/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert "Pro subscription required" in resp.json()["detail"]

    def test_free_user_cannot_create_alert(self, client, _db_session):
        token = _register(client)
        resp = client.post("/api/v1/alerts/", json={
            "name": "Test alert",
            "make": "Ram",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_pro_user_can_save_vehicle(self, client, _db_session):
        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")
        resp = client.post("/api/v1/saved/", json={
            "vin": "1C6SRFFT5PN123456",
            "make": "Ram",
            "model": "Ram 2500",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201

    def test_pro_user_can_create_alert(self, client, _db_session):
        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")
        resp = client.post("/api/v1/alerts/", json={
            "name": "Ram deals",
            "make": "Ram",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201

    def test_scoring_still_free(self, client):
        """POST /score should work without any auth."""
        resp = client.post("/api/v1/score", json={
            "asking_price": 55000,
            "msrp": 65000,
            "make": "Ram",
            "model": "Ram 2500",
            "year": 2025,
            "days_on_lot": 90,
        })
        assert resp.status_code == 200
        assert "score" in resp.json()

    def test_health_still_free(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestCheckout:
    @patch("backend.services.stripe_service._get_stripe")
    def test_checkout_creates_session(self, mock_get_stripe, client, _db_session):
        token = _register(client)

        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_new123")
        mock_stripe.checkout.Session.create.return_value = MagicMock(
            url="https://checkout.stripe.com/test_session"
        )

        resp = client.post("/subscription/checkout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert "checkout_url" in resp.json()
        assert "stripe.com" in resp.json()["checkout_url"]

    def test_checkout_requires_auth(self, client):
        resp = client.post("/subscription/checkout")
        assert resp.status_code == 401

    def test_checkout_already_pro(self, client, _db_session):
        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")
        resp = client.post("/subscription/checkout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409
        assert "Already subscribed" in resp.json()["detail"]

    def test_checkout_past_due_blocked(self, client, _db_session):
        """Past-due users should be directed to billing portal, not create new checkout."""
        token = _register(client)
        _set_past_due(_db_session, "sub@example.com")
        resp = client.post("/subscription/checkout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409
        assert "past due" in resp.json()["detail"]


class TestWebhook:
    def test_webhook_missing_signature(self, client):
        resp = client.post("/webhooks/stripe", content=b'{}')
        assert resp.status_code == 400
        assert "Missing Stripe-Signature" in resp.json()["detail"]

    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_checkout_completed(self, mock_get_stripe, client, _db_session):
        """Webhook should upgrade user to Pro when checkout completes."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        # Register user and set their stripe_customer_id
        token = _register(client)
        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        user.stripe_customer_id = "cus_webhook_test"
        user_id = user.id  # Capture before closing session
        db.commit()
        db.close()

        # Mock the webhook event
        mock_stripe.Webhook.construct_event.return_value = {
            "id": "evt_test_checkout_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_webhook_test",
                    "subscription": "sub_webhook_test",
                    "metadata": {"dealhawk_user_id": str(user_id)},
                }
            }
        }

        resp = client.post(
            "/webhooks/stripe",
            content=b'{"type": "checkout.session.completed"}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp.status_code == 200
        assert resp.json()["received"] is True

        # Verify user is now Pro
        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        assert user.subscription_tier == "pro"
        assert user.subscription_status == "active"
        assert user.subscription_stripe_id == "sub_webhook_test"
        db.close()

    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_idempotency(self, mock_get_stripe, client, _db_session):
        """Duplicate webhook events should be skipped."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        token = _register(client)
        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        user.stripe_customer_id = "cus_idemp_test"
        user_id = user.id  # Capture before closing session
        db.commit()
        db.close()

        mock_stripe.Webhook.construct_event.return_value = {
            "id": "evt_idemp_test_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_idemp_test",
                    "subscription": "sub_idemp_test",
                    "metadata": {"dealhawk_user_id": str(user_id)},
                }
            }
        }

        # First call — should process
        resp1 = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp1.status_code == 200

        # Verify event was recorded
        db = _db_session()
        event = db.query(ProcessedWebhookEvent).filter(
            ProcessedWebhookEvent.event_id == "evt_idemp_test_1"
        ).first()
        assert event is not None
        db.close()

        # Second call with same event ID — should skip
        resp2 = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["received"] is True

    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_metadata_mismatch_rejected(self, mock_get_stripe, client, _db_session):
        """Checkout with mismatched metadata should not activate subscription."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        token = _register(client)
        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        user.stripe_customer_id = "cus_mismatch_test"
        db.commit()
        user_id = user.id
        db.close()

        # Metadata says a different user ID
        mock_stripe.Webhook.construct_event.return_value = {
            "id": "evt_mismatch_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_mismatch_test",
                    "subscription": "sub_mismatch_test",
                    "metadata": {"dealhawk_user_id": "99999"},  # Wrong user
                }
            }
        }

        resp = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp.status_code == 200  # 200 to Stripe so it doesn't retry

        # User should NOT have been upgraded
        db = _db_session()
        user = db.query(User).filter(User.id == user_id).first()
        assert user.subscription_tier != "pro"
        db.close()


    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_subscription_updated_unknown_status(self, mock_get_stripe, client, _db_session):
        """Unknown Stripe status should map to 'expired' and downgrade to free."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")

        mock_stripe.Webhook.construct_event.return_value = {
            "id": "evt_updated_unknown_1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_test123",
                    "status": "some_future_stripe_status",
                    "current_period_end": 1740000000,
                }
            }
        }

        resp = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp.status_code == 200

        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        assert user.subscription_status == "expired"
        assert user.subscription_tier == "free"
        db.close()

    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_subscription_deleted(self, mock_get_stripe, client, _db_session):
        """Subscription deleted should downgrade user to free."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")

        mock_stripe.Webhook.construct_event.return_value = {
            "id": "evt_deleted_1",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer": "cus_test123",
                }
            }
        }

        resp = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp.status_code == 200

        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        assert user.subscription_tier == "free"
        assert user.subscription_status == "canceled"
        assert user.subscription_stripe_id is None
        db.close()

    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_invoice_payment_failed(self, mock_get_stripe, client, _db_session):
        """Invoice payment failed should set user to past_due."""
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe

        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")

        mock_stripe.Webhook.construct_event.return_value = {
            "id": "evt_payment_failed_1",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_test123",
                }
            }
        }

        resp = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "t=1234,v1=abc123"},
        )
        assert resp.status_code == 200

        db = _db_session()
        user = db.query(User).filter(User.email == "sub@example.com").first()
        assert user.subscription_status == "past_due"
        db.close()


class TestProductionValidation:
    def test_validate_production_missing_stripe_secret(self):
        """Production should fail if STRIPE_SECRET_KEY not set."""
        from backend.config.settings import Settings
        s = Settings(environment="production", jwt_secret_key="real-secret-here",
                     stripe_secret_key="", stripe_webhook_secret="whsec_test",
                     stripe_pro_price_id="price_test", base_url="https://api.example.com")
        with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
            s.validate_production()

    def test_validate_production_missing_webhook_secret(self):
        """Production should fail if STRIPE_WEBHOOK_SECRET not set."""
        from backend.config.settings import Settings
        s = Settings(environment="production", jwt_secret_key="real-secret-here",
                     stripe_secret_key="sk_test", stripe_webhook_secret="",
                     stripe_pro_price_id="price_test", base_url="https://api.example.com")
        with pytest.raises(ValueError, match="STRIPE_WEBHOOK_SECRET"):
            s.validate_production()

    def test_validate_production_missing_price_id(self):
        """Production should fail if STRIPE_PRO_PRICE_ID not set."""
        from backend.config.settings import Settings
        s = Settings(environment="production", jwt_secret_key="real-secret-here",
                     stripe_secret_key="sk_test", stripe_webhook_secret="whsec_test",
                     stripe_pro_price_id="", base_url="https://api.example.com")
        with pytest.raises(ValueError, match="STRIPE_PRO_PRICE_ID"):
            s.validate_production()

    def test_validate_production_missing_base_url(self):
        """Production should fail if BASE_URL not set."""
        from backend.config.settings import Settings
        s = Settings(environment="production", jwt_secret_key="real-secret-here",
                     stripe_secret_key="sk_test", stripe_webhook_secret="whsec_test",
                     stripe_pro_price_id="price_test", base_url="")
        with pytest.raises(ValueError, match="BASE_URL"):
            s.validate_production()

    def test_validate_production_all_set_passes(self):
        """Production with all settings should not raise."""
        from backend.config.settings import Settings
        s = Settings(environment="production", jwt_secret_key="real-secret-here",
                     stripe_secret_key="sk_test", stripe_webhook_secret="whsec_test",
                     stripe_pro_price_id="price_test", base_url="https://api.example.com",
                     dealer_api_key_salt="production-salt-value",
                     redis_url="redis://localhost:6379/0")
        s.validate_production()  # Should not raise


class TestHTMLPages:
    def test_success_page_has_csp(self, client):
        resp = client.get("/subscription/success")
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        assert "X-Frame-Options" in resp.headers
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_cancel_page_has_csp(self, client):
        resp = client.get("/subscription/cancel")
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        assert "X-Frame-Options" in resp.headers


class TestMeEndpoint:
    def test_me_shows_subscription(self, client, _db_session):
        token = _register(client)
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["subscription_tier"] == "free"
        assert data["subscription_status"] == "active"

    def test_me_shows_pro(self, client, _db_session):
        token = _register(client)
        _upgrade_to_pro(_db_session, "sub@example.com")
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["subscription_tier"] == "pro"


class TestCanceledProAccess:

    def test_canceled_pro_blocked_from_saved(self, client, _db_session):
        """A Pro user whose subscription was canceled should be blocked from Pro features."""
        token = _register(client, email="canceled@example.com")
        db = _db_session()
        user = db.query(User).filter(User.email == "canceled@example.com").first()
        user.subscription_tier = "pro"
        user.subscription_status = "canceled"
        user.stripe_customer_id = "cus_canceled"
        db.commit()
        db.close()

        resp = client.get("/api/v1/saved/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_past_due_allowed_saved_access(self, client, _db_session):
        """A past_due Pro user should still have access to Pro features (grace period)."""
        token = _register(client, email="pastdue@example.com")
        _set_past_due(_db_session, "pastdue@example.com")
        resp = client.get("/api/v1/saved/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    @patch("backend.services.stripe_service._get_stripe")
    def test_webhook_signature_verification_error(self, mock_get_stripe, client):
        """Invalid webhook signature should return 400."""
        import stripe as stripe_module
        mock_stripe = MagicMock()
        mock_get_stripe.return_value = mock_stripe
        mock_stripe.Webhook.construct_event.side_effect = stripe_module.SignatureVerificationError(
            "Invalid signature", sig_header="t=bad,v1=invalid"
        )

        resp = client.post(
            "/webhooks/stripe",
            content=b'{"type": "checkout.session.completed"}',
            headers={"Stripe-Signature": "t=bad,v1=invalid"},
        )
        assert resp.status_code == 400
        assert "Signature verification" in resp.json()["detail"]
