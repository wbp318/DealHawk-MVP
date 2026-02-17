"""Celery task for batch VIN decoding."""

import asyncio
import logging

from backend.celery_app import app
from backend.database.db import SessionLocal
from backend.services.vin_decoder import decode_vin

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=10)
def decode_vin_batch(self, vins: list[str], dealer_id: int | None = None):
    """Decode a batch of VINs. Results stored in vehicles table via existing caching.

    Returns summary dict: {decoded, failed, errors}.
    """
    db = SessionLocal()
    decoded = 0
    failed = 0
    errors = []

    try:
        for vin in vins:
            try:
                asyncio.run(decode_vin(vin, db=db))
                decoded += 1
            except Exception as exc:
                failed += 1
                errors.append({"vin": vin, "error": str(exc)})
                logger.warning("VIN decode failed for %s: %s", vin, exc)

        logger.info(
            "Batch VIN decode complete: %d decoded, %d failed (dealer_id=%s)",
            decoded, failed, dealer_id,
        )
        return {"decoded": decoded, "failed": failed, "errors": errors}
    except Exception as exc:
        logger.exception("Batch VIN decode task failed")
        raise self.retry(exc=exc)
    finally:
        db.close()
