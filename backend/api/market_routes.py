"""Consumer market data endpoints — free tier, no auth required."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.marketcheck_service import get_market_trends, get_market_stats

logger = logging.getLogger(__name__)

market_router = APIRouter(prefix="/market", tags=["market"])


@market_router.get("/trends/{make}/{model}")
def market_trends(
    make: str = Path(..., min_length=1, max_length=50),
    model: str = Path(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    """Get market trend data for a make/model (days supply, price trend, incentives)."""
    try:
        return get_market_trends(make, model, db)
    except Exception:
        logger.exception("Market trends fetch failed for %s %s", make, model)
        raise HTTPException(status_code=502, detail="Market data service temporarily unavailable")


@market_router.get("/stats/{make}/{model}")
def market_stats(
    make: str = Path(..., min_length=1, max_length=50),
    model: str = Path(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    """Get market stats for a make/model (avg price, listings, days on lot)."""
    try:
        return get_market_stats(make, model, db)
    except Exception:
        logger.exception("Market stats fetch failed for %s %s", make, model)
        raise HTTPException(status_code=502, detail="Market data service temporarily unavailable")
