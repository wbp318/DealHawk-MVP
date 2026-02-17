"""Tests for Celery tasks — webhook, alert, market cache, VIN batch."""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta

from backend.database.models import Base, User, DealAlert, MarketDataCache, Dealership
from backend.api.dealer_auth import _hash_api_key


TEST_API_KEY = "dh_dealer_test_key_celery_12345678901234"


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
def db(test_session):
    session = test_session()
    yield session
    session.close()


# --- Webhook task tests ---

class TestWebhookTask:

    @patch("backend.tasks.webhook_tasks.process_checkout_completed")
    @patch("backend.tasks.webhook_tasks.SessionLocal")
    def test_processes_checkout_completed(self, mock_session_local, mock_process):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        from backend.tasks.webhook_tasks import process_webhook_event
        result = process_webhook_event("evt_123", "checkout.session.completed", {"customer": "cus_123"})

        mock_process.assert_called_once_with({"customer": "cus_123"}, mock_db)
        assert result["status"] == "processed"

    @patch("backend.tasks.webhook_tasks.SessionLocal")
    def test_skips_unknown_event_type(self, mock_session_local):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        from backend.tasks.webhook_tasks import process_webhook_event
        result = process_webhook_event("evt_456", "unknown.event", {})

        assert result["status"] == "skipped"

    @patch("backend.tasks.webhook_tasks.process_subscription_updated")
    @patch("backend.tasks.webhook_tasks.SessionLocal")
    def test_processes_subscription_updated(self, mock_session_local, mock_process):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        from backend.tasks.webhook_tasks import process_webhook_event
        result = process_webhook_event("evt_789", "customer.subscription.updated", {"id": "sub_123"})

        mock_process.assert_called_once()
        assert result["status"] == "processed"


# --- Alert task tests ---

class TestAlertTask:

    @patch("backend.tasks.alert_tasks.send_alert_email")
    @patch("backend.tasks.alert_tasks.SessionLocal")
    def test_sends_email_on_match(self, mock_session_local, mock_send_task, test_session):
        db = test_session()
        user = User(email="user@test.com", hashed_password="hashed", subscription_tier="pro")
        db.add(user)
        db.commit()
        db.refresh(user)

        alert = DealAlert(
            user_id=user.id, name="Ram Alert", make="Ram", model="1500",
            year_min=2024, price_max=60000, score_min=50, is_active=True,
        )
        db.add(alert)
        db.commit()
        db.close()

        mock_session_local.return_value = test_session()
        mock_send_task.delay = MagicMock()

        from backend.tasks.alert_tasks import check_and_notify_alerts
        result = check_and_notify_alerts({
            "make": "Ram", "model": "1500", "year": 2025,
            "asking_price": 55000, "deal_score": 70, "days_on_lot": 90,
        })

        assert result["matches"] == 1
        mock_send_task.delay.assert_called_once()

    @patch("backend.tasks.alert_tasks.send_alert_email")
    @patch("backend.tasks.alert_tasks.SessionLocal")
    def test_no_email_on_non_match(self, mock_session_local, mock_send_task, test_session):
        db = test_session()
        user = User(email="user@test.com", hashed_password="hashed", subscription_tier="pro")
        db.add(user)
        db.commit()
        db.refresh(user)

        alert = DealAlert(
            user_id=user.id, name="Ford Alert", make="Ford", model="F-150",
            score_min=80, is_active=True,
        )
        db.add(alert)
        db.commit()
        db.close()

        mock_session_local.return_value = test_session()
        mock_send_task.delay = MagicMock()

        from backend.tasks.alert_tasks import check_and_notify_alerts
        result = check_and_notify_alerts({
            "make": "Ram", "model": "1500", "year": 2025,
            "asking_price": 55000, "deal_score": 70, "days_on_lot": 30,
        })

        assert result["matches"] == 0
        mock_send_task.delay.assert_not_called()


# --- Market cache task tests ---

class TestMarketCacheTask:

    @patch("backend.tasks.market_tasks.get_market_trends")
    @patch("backend.tasks.market_tasks.SessionLocal")
    def test_refreshes_cache_entries(self, mock_session_local, mock_trends, test_session):
        db = test_session()
        # Add an expired cache entry
        db.add(MarketDataCache(
            cache_key="trends:Ram:1500", make="Ram", model="1500",
            data_type="trends", response_json="{}",
            fetched_at=datetime.utcnow() - timedelta(hours=48),
            expires_at=datetime.utcnow() - timedelta(hours=24),
        ))
        db.commit()
        db.close()

        mock_session_local.return_value = test_session()
        mock_trends.return_value = {"source": "stub"}

        from backend.tasks.market_tasks import refresh_market_cache
        result = refresh_market_cache()

        assert result["refreshed"] == 1
        mock_trends.assert_called_once()


# --- VIN batch task tests ---

class TestVinBatchTask:

    @patch("backend.tasks.vin_tasks.decode_vin")
    @patch("backend.tasks.vin_tasks.SessionLocal")
    def test_batch_decode_success(self, mock_session_local, mock_decode):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_decode.return_value = {"vin": "1C6SRFFT8PN123456"}

        from backend.tasks.vin_tasks import decode_vin_batch
        result = decode_vin_batch(["1C6SRFFT8PN123456", "3C63RRGL5PG654321"])

        assert result["decoded"] == 2
        assert result["failed"] == 0

    @patch("backend.tasks.vin_tasks.decode_vin")
    @patch("backend.tasks.vin_tasks.SessionLocal")
    def test_batch_decode_partial_failure(self, mock_session_local, mock_decode):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_decode.side_effect = [
            {"vin": "1C6SRFFT8PN123456"},
            ValueError("Invalid VIN"),
        ]

        from backend.tasks.vin_tasks import decode_vin_batch
        result = decode_vin_batch(["1C6SRFFT8PN123456", "BADVIN12345678901"])

        assert result["decoded"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1


# --- Webhook route dispatch tests ---

class TestWebhookRouteDispatch:

    @pytest.fixture
    def client_no_redis(self, test_session):
        with patch("backend.database.db.SessionLocal", test_session):
            with patch("backend.api.webhook_routes.get_settings") as mock_settings:
                settings = mock_settings.return_value
                settings.redis_url = ""
                from backend.api.app import create_app
                from fastapi.testclient import TestClient
                app = create_app()
                yield TestClient(app)

    @patch("backend.api.webhook_routes.handle_webhook_event")
    def test_webhook_sync_without_redis(self, mock_handle, client_no_redis):
        mock_handle.return_value = {
            "id": "evt_test",
            "type": "checkout.session.completed",
            "data": {"object": {"customer": "cus_test"}},
        }

        with patch("backend.api.webhook_routes.process_checkout_completed"):
            response = client_no_redis.post(
                "/webhooks/stripe",
                content=b"test_payload",
                headers={"Stripe-Signature": "test_sig"},
            )

        assert response.status_code == 200
        assert response.json()["received"] is True


# --- Dealer batch VIN route tests ---

class TestDealerBatchVinRoute:

    @pytest.fixture
    def client_with_dealer(self, test_session):
        db = test_session()
        dealer = Dealership(
            name="Test Dealer", email="batch@dealer.com",
            api_key_hash=_hash_api_key(TEST_API_KEY),
            is_active=True, tier="standard",
            daily_rate_limit=1000, monthly_rate_limit=25000,
            requests_today=0, requests_this_month=0,
        )
        db.add(dealer)
        db.commit()
        db.close()

        with patch("backend.database.db.SessionLocal", test_session):
            from backend.api.app import create_app
            from fastapi.testclient import TestClient
            app = create_app()
            yield TestClient(app)

    @patch("backend.api.dealer_routes.get_settings")
    @patch("backend.services.vin_decoder.decode_vin")
    def test_batch_vin_sync_without_redis(self, mock_decode, mock_settings, client_with_dealer):
        mock_settings.return_value.redis_url = ""
        mock_decode.return_value = {"vin": "1C6SRFFT8PN123456"}

        response = client_with_dealer.post(
            "/api/v1/dealer/vin/batch",
            json={"vins": ["1C6SRFFT8PN123456"]},
            headers={"X-API-Key": TEST_API_KEY},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_batch_vin_rejects_invalid_vin(self, client_with_dealer):
        response = client_with_dealer.post(
            "/api/v1/dealer/vin/batch",
            json={"vins": ["INVALID"]},
            headers={"X-API-Key": TEST_API_KEY},
        )

        assert response.status_code == 400
