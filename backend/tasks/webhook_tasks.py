"""Celery task for processing Stripe webhook events asynchronously."""

import logging

from backend.celery_app import app
from backend.database.db import SessionLocal
from backend.services.stripe_service import (
    process_checkout_completed,
    process_subscription_updated,
    process_subscription_deleted,
    process_invoice_payment_failed,
)

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_webhook_event(self, event_id: str, event_type: str, event_data: dict):
    """Process a verified, deduplicated Stripe webhook event."""
    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            process_checkout_completed(event_data, db)
        elif event_type == "customer.subscription.updated":
            process_subscription_updated(event_data, db)
        elif event_type == "customer.subscription.deleted":
            process_subscription_deleted(event_data, db)
        elif event_type == "invoice.payment_failed":
            process_invoice_payment_failed(event_data, db)
        else:
            logger.info("Unhandled webhook event type in task: %s (id: %s)", event_type, event_id)
            return {"status": "skipped", "event_type": event_type}

        logger.info("Processed webhook event %s (%s) via Celery", event_id, event_type)
        return {"status": "processed", "event_id": event_id, "event_type": event_type}
    except Exception as exc:
        logger.exception("Webhook task failed for event %s (%s)", event_id, event_type)
        raise self.retry(exc=exc)
    finally:
        db.close()
