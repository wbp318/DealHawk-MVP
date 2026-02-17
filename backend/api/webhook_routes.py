"""Stripe webhook endpoint — separate router for raw body parsing."""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import ProcessedWebhookEvent
from backend.services.stripe_service import (
    handle_webhook_event,
    process_checkout_completed,
    process_subscription_updated,
    process_subscription_deleted,
    process_invoice_payment_failed,
)

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhook_router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events. No auth — verified by Stripe signature."""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = handle_webhook_event(payload, sig_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Signature verification failed")

    event_id = event.get("id")
    event_type = event.get("type", "")

    # Idempotency: skip already-processed events (Stripe retries on timeout/5xx)
    if event_id:
        existing = db.query(ProcessedWebhookEvent).filter(
            ProcessedWebhookEvent.event_id == event_id
        ).first()
        if existing:
            logger.info("Skipping duplicate webhook event: %s (%s)", event_id, event_type)
            return {"received": True}

    event_data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        process_checkout_completed(event_data, db)
    elif event_type == "customer.subscription.updated":
        process_subscription_updated(event_data, db)
    elif event_type == "customer.subscription.deleted":
        process_subscription_deleted(event_data, db)
    elif event_type == "invoice.payment_failed":
        process_invoice_payment_failed(event_data, db)
    else:
        logger.info("Unhandled webhook event type: %s (id: %s)", event_type, event_id)

    # Record event as processed (IntegrityError = concurrent duplicate, safe to ignore)
    if event_id:
        try:
            db.add(ProcessedWebhookEvent(event_id=event_id, event_type=event_type))
            db.commit()
        except IntegrityError:
            db.rollback()

    return {"received": True}
