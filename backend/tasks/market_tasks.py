"""Celery task for refreshing MarketCheck data cache on a schedule."""

import logging
from datetime import datetime

from backend.celery_app import app
from backend.database.db import SessionLocal
from backend.database.models import MarketDataCache
from backend.services.marketcheck_service import get_market_trends, get_market_stats

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=1, default_retry_delay=300)
def refresh_market_cache(self):
    """Refresh expired market data cache entries.

    Runs on beat schedule (every 6 hours). Queries distinct (make, model, data_type)
    from cache, deletes expired entries, and re-fetches fresh data.
    """
    db = SessionLocal()
    try:
        # Find distinct cache entries to refresh
        entries = (
            db.query(
                MarketDataCache.make,
                MarketDataCache.model,
                MarketDataCache.data_type,
            )
            .distinct()
            .all()
        )

        refreshed = 0
        failed = 0

        for make, model, data_type in entries:
            try:
                # Delete expired entries for this key
                db.query(MarketDataCache).filter(
                    MarketDataCache.make == make,
                    MarketDataCache.model == model,
                    MarketDataCache.data_type == data_type,
                    MarketDataCache.expires_at <= datetime.utcnow(),
                ).delete()
                db.commit()

                # Re-fetch (this will re-populate cache via _store_cache)
                if data_type == "trends":
                    get_market_trends(make, model, db)
                elif data_type == "stats":
                    get_market_stats(make, model, db)

                refreshed += 1
            except Exception:
                failed += 1
                logger.exception("Failed to refresh cache for %s %s (%s)", make, model, data_type)
                db.rollback()

        logger.info("Market cache refresh: %d refreshed, %d failed out of %d entries", refreshed, failed, len(entries))
        return {"refreshed": refreshed, "failed": failed, "total": len(entries)}
    except Exception as exc:
        logger.exception("Market cache refresh task failed")
        raise self.retry(exc=exc)
    finally:
        db.close()
