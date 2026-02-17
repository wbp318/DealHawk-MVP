"""
MarketCheck service — market trends and stats with DB caching.

Uses stub data from existing MODEL_DAYS_SUPPLY and seeded incentives when
no MarketCheck API key is configured. Clean interface to swap in live API.

Live API path includes: retry with exponential backoff, circuit breaker,
explicit timeouts, and graceful fallback to stubs on failure.
"""

import json
import logging
import time
from datetime import datetime, timedelta

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.config.invoice_ranges import INVOICE_RATIOS, DEFAULT_INVOICE_RATIO, TRIM_THRESHOLDS
from backend.database.models import MarketDataCache, IncentiveProgram
from backend.services.deal_scorer import MODEL_DAYS_SUPPLY, INDUSTRY_AVG_DAYS_SUPPLY

logger = logging.getLogger(__name__)


# --- Circuit breaker state ---

_circuit_failure_count = 0
_circuit_opened_at: float | None = None
_CIRCUIT_FAILURE_THRESHOLD = 5
_CIRCUIT_RESET_TIMEOUT = 300  # 5 minutes


class MarketCheckUnavailableError(Exception):
    """Raised when circuit breaker is open."""
    pass


def _check_circuit():
    """Raise if circuit breaker is open (not yet timed out)."""
    global _circuit_opened_at
    if _circuit_opened_at is not None:
        elapsed = time.time() - _circuit_opened_at
        if elapsed < _CIRCUIT_RESET_TIMEOUT:
            raise MarketCheckUnavailableError("Circuit breaker open — MarketCheck API unavailable")
        # Timeout elapsed, allow a probe request (half-open)
        _circuit_opened_at = None


def _record_success():
    """Reset circuit breaker on success."""
    global _circuit_failure_count, _circuit_opened_at
    _circuit_failure_count = 0
    _circuit_opened_at = None


def _record_failure():
    """Increment failure count, open circuit if threshold reached."""
    global _circuit_failure_count, _circuit_opened_at
    _circuit_failure_count += 1
    if _circuit_failure_count >= _CIRCUIT_FAILURE_THRESHOLD:
        _circuit_opened_at = time.time()
        logger.warning("Circuit breaker OPENED after %d consecutive failures", _circuit_failure_count)


def reset_circuit_breaker():
    """Reset circuit breaker state (for testing)."""
    global _circuit_failure_count, _circuit_opened_at
    _circuit_failure_count = 0
    _circuit_opened_at = None


# --- Public API ---

def get_market_trends(make: str, model: str, db: Session) -> dict:
    """Get market trend data for a make/model. Uses cache, then stub or live API."""
    cache_key = f"trends:{make}:{model}"
    cached = _check_cache(cache_key, db)
    if cached is not None:
        return cached

    settings = get_settings()
    if settings.marketcheck_api_key:
        data = _fetch_trends_live(make, model, settings, db)
    else:
        data = _stub_trends(make, model, db)

    _store_cache(cache_key, make, model, "trends", data, db)
    return data


def get_market_stats(make: str, model: str, db: Session) -> dict:
    """Get market stats (pricing, listings) for a make/model."""
    cache_key = f"stats:{make}:{model}"
    cached = _check_cache(cache_key, db)
    if cached is not None:
        return cached

    settings = get_settings()
    if settings.marketcheck_api_key:
        data = _fetch_stats_live(make, model, settings, db)
    else:
        data = _stub_stats(make, model)

    _store_cache(cache_key, make, model, "stats", data, db)
    return data


# --- Cache helpers ---

def _check_cache(cache_key: str, db: Session) -> dict | None:
    """Return cached response if not expired, else None."""
    entry = db.query(MarketDataCache).filter(
        MarketDataCache.cache_key == cache_key,
        MarketDataCache.expires_at > datetime.utcnow(),
    ).first()
    if entry:
        return json.loads(entry.response_json)
    return None


def _store_cache(cache_key: str, make: str, model: str, data_type: str, data: dict, db: Session) -> None:
    """Store or update cache entry."""
    settings = get_settings()
    ttl = timedelta(hours=settings.marketcheck_cache_ttl_hours)
    now = datetime.utcnow()

    existing = db.query(MarketDataCache).filter(
        MarketDataCache.cache_key == cache_key
    ).first()

    if existing:
        existing.response_json = json.dumps(data)
        existing.fetched_at = now
        existing.expires_at = now + ttl
    else:
        db.add(MarketDataCache(
            cache_key=cache_key,
            make=make,
            model=model,
            data_type=data_type,
            response_json=json.dumps(data),
            fetched_at=now,
            expires_at=now + ttl,
        ))
    db.commit()


# --- Stub implementations ---

def _stub_trends(make: str, model: str, db: Session) -> dict:
    """Build trend data from existing MODEL_DAYS_SUPPLY and seeded incentives."""
    days_supply = MODEL_DAYS_SUPPLY.get(model)
    if days_supply is None:
        for key, val in MODEL_DAYS_SUPPLY.items():
            if key in model or model in key:
                days_supply = val
                break
    if days_supply is None:
        days_supply = INDUSTRY_AVG_DAYS_SUPPLY

    supply_ratio = days_supply / INDUSTRY_AVG_DAYS_SUPPLY

    if supply_ratio > 1.3:
        supply_level = "oversupplied"
        price_trend = "declining"
    elif supply_ratio < 0.7:
        supply_level = "undersupplied"
        price_trend = "rising"
    else:
        supply_level = "balanced"
        price_trend = "stable"

    # Count active incentives from DB
    query = db.query(IncentiveProgram).filter(IncentiveProgram.make == make)
    if model:
        query = query.filter(
            (IncentiveProgram.model == model) | (IncentiveProgram.model.is_(None))
        )
    incentives = query.all()
    active_count = len(incentives)
    total_value = sum(i.amount or 0 for i in incentives)

    if supply_ratio > 1.3:
        inventory_level = "high"
    elif supply_ratio < 0.7:
        inventory_level = "low"
    else:
        inventory_level = "moderate"

    return {
        "make": make,
        "model": model,
        "days_supply": days_supply,
        "industry_avg_days_supply": INDUSTRY_AVG_DAYS_SUPPLY,
        "supply_ratio": round(supply_ratio, 2),
        "supply_level": supply_level,
        "price_trend": price_trend,
        "active_incentive_count": active_count,
        "total_incentive_value": total_value,
        "inventory_level": inventory_level,
        "source": "stub",
        "as_of": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def _stub_stats(make: str, model: str) -> dict:
    """Build estimated price stats from invoice_ranges.py ratios."""
    ratios = INVOICE_RATIOS.get(f"{make} {model}") or INVOICE_RATIOS.get(model)
    thresholds = TRIM_THRESHOLDS.get(model, {"base_max": 45000, "high_min": 70000})

    if ratios:
        base_msrp = thresholds["base_max"]
        high_msrp = thresholds["high_min"]
        avg_msrp = (base_msrp + high_msrp) / 2
        low_price = round(base_msrp * ratios["base"], 0)
        high_price = round(high_msrp * 1.05, 0)  # Above MSRP for loaded trims
    else:
        avg_msrp = 55000
        low_price = round(avg_msrp * DEFAULT_INVOICE_RATIO, 0)
        high_price = round(avg_msrp * 1.1, 0)

    days_supply = MODEL_DAYS_SUPPLY.get(model)
    if days_supply is None:
        for key, val in MODEL_DAYS_SUPPLY.items():
            if key in model or model in key:
                days_supply = val
                break
    median_days = min(days_supply or 45, 120)

    return {
        "make": make,
        "model": model,
        "avg_price": round(avg_msrp, 0),
        "price_range_low": low_price,
        "price_range_high": high_price,
        "median_days_on_lot": median_days,
        "total_active_listings": 0,  # Stub: no real listing count
        "source": "stub",
        "as_of": datetime.utcnow().strftime("%Y-%m-%d"),
    }


# --- Real API with retry + circuit breaker ---

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
)
def _fetch_trends_from_api(make: str, model: str, settings) -> dict:
    """Fetch trends from MarketCheck API with retries."""
    url = f"{settings.marketcheck_base_url}/trends/{make}/{model}"
    headers = {"Authorization": settings.marketcheck_api_key}
    resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
    resp.raise_for_status()
    raw = resp.json()

    return {
        "make": make,
        "model": model,
        "days_supply": raw.get("days_supply", INDUSTRY_AVG_DAYS_SUPPLY),
        "industry_avg_days_supply": INDUSTRY_AVG_DAYS_SUPPLY,
        "supply_ratio": round(raw.get("days_supply", INDUSTRY_AVG_DAYS_SUPPLY) / INDUSTRY_AVG_DAYS_SUPPLY, 2),
        "supply_level": raw.get("supply_level", "balanced"),
        "price_trend": raw.get("price_trend", "stable"),
        "active_incentive_count": raw.get("incentive_count", 0),
        "total_incentive_value": raw.get("incentive_value", 0),
        "inventory_level": raw.get("inventory_level", "moderate"),
        "source": "marketcheck",
        "as_of": datetime.utcnow().strftime("%Y-%m-%d"),
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
)
def _fetch_stats_from_api(make: str, model: str, settings) -> dict:
    """Fetch market stats from MarketCheck API with retries."""
    url = f"{settings.marketcheck_base_url}/stats/{make}/{model}"
    headers = {"Authorization": settings.marketcheck_api_key}
    resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
    resp.raise_for_status()
    raw = resp.json()

    return {
        "make": make,
        "model": model,
        "avg_price": raw.get("avg_price", 0),
        "price_range_low": raw.get("price_range_low", 0),
        "price_range_high": raw.get("price_range_high", 0),
        "median_days_on_lot": raw.get("median_days_on_lot", 0),
        "total_active_listings": raw.get("total_active_listings", 0),
        "source": "marketcheck",
        "as_of": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def _fetch_trends_live(make: str, model: str, settings, db: Session) -> dict:
    """Fetch trends with circuit breaker. Falls back to stub on failure."""
    try:
        _check_circuit()
        data = _fetch_trends_from_api(make, model, settings)
        _record_success()
        return data
    except MarketCheckUnavailableError:
        logger.warning("Circuit open — using stub trends for %s %s", make, model)
        return _stub_trends(make, model, db)
    except Exception:
        _record_failure()
        logger.warning("MarketCheck trends API failed for %s %s — falling back to stub", make, model)
        return _stub_trends(make, model, db)


def _fetch_stats_live(make: str, model: str, settings, db: Session) -> dict:
    """Fetch stats with circuit breaker. Falls back to stub on failure."""
    try:
        _check_circuit()
        data = _fetch_stats_from_api(make, model, settings)
        _record_success()
        return data
    except MarketCheckUnavailableError:
        logger.warning("Circuit open — using stub stats for %s %s", make, model)
        return _stub_stats(make, model)
    except Exception:
        _record_failure()
        logger.warning("MarketCheck stats API failed for %s %s — falling back to stub", make, model)
        return _stub_stats(make, model)
