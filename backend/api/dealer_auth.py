"""Dealer API key authentication and rate limiting."""

import hashlib
import hmac
from datetime import date

from fastapi import Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.db import get_db
from backend.database.models import Dealership


def _hash_api_key(api_key: str) -> str:
    """SHA-256 hash with salt for API key storage."""
    settings = get_settings()
    salted = f"{settings.dealer_api_key_salt}:{api_key}"
    return hashlib.sha256(salted.encode()).hexdigest()


def get_dealership_required(
    request: Request, db: Session = Depends(get_db)
) -> Dealership:
    """FastAPI dependency: validate X-API-Key header, enforce rate limits."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required (X-API-Key header)")

    key_hash = _hash_api_key(api_key)

    # Fetch all active dealers and compare hashes in constant time
    # to prevent timing-based API key enumeration
    active_dealers = db.query(Dealership).filter(Dealership.is_active == True).all()
    dealer = None
    for d in active_dealers:
        if hmac.compare_digest(d.api_key_hash, key_hash):
            dealer = d
            break

    if not dealer:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Reset counters if new day/month
    today = date.today()
    current_month = today.strftime("%Y-%m")

    if dealer.last_request_date != today:
        dealer.requests_today = 0
        dealer.last_request_date = today

    if dealer.last_request_month != current_month:
        dealer.requests_this_month = 0
        dealer.last_request_month = current_month

    # Check rate limits
    if dealer.requests_today >= dealer.daily_rate_limit:
        raise HTTPException(
            status_code=429,
            detail="Daily rate limit exceeded",
            headers={"Retry-After": "86400"},
        )

    if dealer.requests_this_month >= dealer.monthly_rate_limit:
        raise HTTPException(
            status_code=429,
            detail="Monthly rate limit exceeded",
            headers={"Retry-After": "86400"},
        )

    # Atomic counter increment to prevent race conditions
    db.execute(
        update(Dealership)
        .where(Dealership.id == dealer.id)
        .values(
            requests_today=Dealership.requests_today + 1,
            requests_this_month=Dealership.requests_this_month + 1,
            last_request_date=today,
            last_request_month=current_month,
        )
    )
    db.commit()

    # Refresh the object so downstream code sees updated values
    db.refresh(dealer)

    return dealer
