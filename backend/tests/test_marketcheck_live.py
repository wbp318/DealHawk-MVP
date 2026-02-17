"""Tests for MarketCheck API hardening — retries, circuit breaker, fallback."""

import pytest
import time
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import httpx

from backend.database.models import Base
from backend.services import marketcheck_service
from backend.services.marketcheck_service import (
    _fetch_trends_from_api,
    _fetch_stats_from_api,
    _fetch_trends_live,
    _fetch_stats_live,
    reset_circuit_breaker,
    _record_failure,
    _record_success,
    _check_circuit,
    MarketCheckUnavailableError,
    _CIRCUIT_FAILURE_THRESHOLD,
)


@pytest.fixture(autouse=True)
def reset_circuit():
    """Reset circuit breaker before each test."""
    reset_circuit_breaker()
    yield
    reset_circuit_breaker()


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


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.marketcheck_api_key = "test_api_key"
    settings.marketcheck_base_url = "https://mc-api.test.com/v2"
    return settings


class TestRetryOnTimeout:

    @patch("backend.services.marketcheck_service.httpx.get")
    def test_retry_on_timeout_then_success(self, mock_get, mock_settings):
        """Two timeouts then success — should return data after retries."""
        good_response = MagicMock()
        good_response.status_code = 200
        good_response.json.return_value = {
            "days_supply": 80,
            "supply_level": "balanced",
            "price_trend": "stable",
        }
        good_response.raise_for_status = MagicMock()

        mock_get.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            good_response,
        ]

        result = _fetch_trends_from_api("Ram", "1500", mock_settings)
        assert result["source"] == "marketcheck"
        assert result["days_supply"] == 80
        assert mock_get.call_count == 3

    @patch("backend.services.marketcheck_service.httpx.get")
    def test_retry_on_500_then_success(self, mock_get, mock_settings):
        """Two 500s then success."""
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=error_response
        )

        good_response = MagicMock()
        good_response.status_code = 200
        good_response.json.return_value = {"avg_price": 55000}
        good_response.raise_for_status = MagicMock()

        mock_get.side_effect = [error_response, error_response, good_response]

        result = _fetch_stats_from_api("Ram", "1500", mock_settings)
        assert result["source"] == "marketcheck"
        assert mock_get.call_count == 3

    @patch("backend.services.marketcheck_service.httpx.get")
    def test_max_retries_exhausted_raises(self, mock_get, mock_settings):
        """All 3 attempts timeout — should raise."""
        mock_get.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(Exception):
            _fetch_trends_from_api("Ram", "1500", mock_settings)

        assert mock_get.call_count == 3


class TestCircuitBreaker:

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit should open after N consecutive failures."""
        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            _record_failure()

        with pytest.raises(MarketCheckUnavailableError):
            _check_circuit()

    def test_circuit_blocks_requests_when_open(self):
        """When circuit is open, _check_circuit should raise."""
        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            _record_failure()

        with pytest.raises(MarketCheckUnavailableError):
            _check_circuit()

    def test_circuit_resets_after_timeout(self):
        """Circuit should close after reset timeout."""
        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            _record_failure()

        # Manually set opened_at to the past
        marketcheck_service._circuit_opened_at = time.time() - 400  # > 300s reset

        # Should not raise — circuit should be half-open
        _check_circuit()

    def test_success_resets_failure_counter(self):
        """_record_success should reset the failure counter."""
        for _ in range(3):
            _record_failure()

        _record_success()

        # Should need full threshold again to open
        for _ in range(_CIRCUIT_FAILURE_THRESHOLD - 1):
            _record_failure()

        # Should still be closed (one less than threshold)
        _check_circuit()  # No exception


class TestLiveFallback:

    @patch("backend.services.marketcheck_service._fetch_trends_from_api")
    @patch("backend.services.marketcheck_service._stub_trends")
    def test_fallback_to_stub_on_api_failure(self, mock_stub, mock_api, mock_settings, db):
        """When API fails after retries, should fall back to stub data."""
        mock_api.side_effect = httpx.TimeoutException("timeout")
        mock_stub.return_value = {"source": "stub", "days_supply": 76}

        result = _fetch_trends_live("Ram", "1500", mock_settings, db)

        assert result["source"] == "stub"
        mock_stub.assert_called_once()

    @patch("backend.services.marketcheck_service._fetch_stats_from_api")
    @patch("backend.services.marketcheck_service._stub_stats")
    def test_stats_fallback_to_stub(self, mock_stub, mock_api, mock_settings, db):
        """Stats API failure falls back to stub."""
        mock_api.side_effect = Exception("Network error")
        mock_stub.return_value = {"source": "stub", "avg_price": 55000}

        result = _fetch_stats_live("Ram", "1500", mock_settings, db)

        assert result["source"] == "stub"

    @patch("backend.services.marketcheck_service._fetch_trends_from_api")
    def test_live_returns_api_data_on_success(self, mock_api, mock_settings, db):
        mock_api.return_value = {"source": "marketcheck", "days_supply": 90}

        result = _fetch_trends_live("Ram", "1500", mock_settings, db)

        assert result["source"] == "marketcheck"
        assert result["days_supply"] == 90
