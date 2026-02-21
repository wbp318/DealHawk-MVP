"""Stripe integration for subscription billing."""

import logging
from datetime import datetime, timezone

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.models import User

logger = logging.getLogger(__name__)

settings = get_settings()

_STATUS_MAP = {
    "active": "active",
    "past_due": "past_due",
    "canceled": "canceled",
    "unpaid": "expired",
    "incomplete": "expired",
    "incomplete_expired": "expired",
    "trialing": "active",
}


def _get_stripe():
    """Return a configured stripe module (avoids module-level api_key assignment)."""
    stripe.api_key = settings.stripe_secret_key
    return stripe


def _get_base_url() -> str:
    """Return the base URL for Stripe redirect URLs."""
    if settings.base_url:
        return settings.base_url.rstrip("/")
    return f"http://localhost:{settings.api_port}"


def get_or_create_stripe_customer(user: User, db: Session) -> str:
    """Return existing Stripe customer ID or create a new one.

    Uses DB unique constraint on stripe_customer_id to prevent race conditions.
    If two requests race, the loser refreshes and uses the winner's customer ID.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    s = _get_stripe()
    customer = s.Customer.create(
        email=user.email,
        metadata={"dealhawk_user_id": str(user.id)},
    )

    user.stripe_customer_id = customer.id
    try:
        db.commit()
    except IntegrityError:
        # Another request won the race — refresh and use their customer ID
        db.rollback()
        db.refresh(user)
        if user.stripe_customer_id:
            # Clean up the orphaned Stripe customer we just created
            try:
                s.Customer.delete(customer.id)
            except Exception:
                logger.warning("Failed to clean up orphaned Stripe customer: %s", customer.id)
            return user.stripe_customer_id
        # If still None after refresh, something is wrong — re-raise
        raise

    return customer.id


def create_checkout_session(
    user: User,
    db: Session,
    return_path: str | None = None,
    cancel_path: str | None = None,
) -> str:
    """Create a Stripe Checkout Session and return the URL.

    Checks both tier and status to prevent duplicate subscriptions.
    Optional return_path/cancel_path override the default redirect URLs.
    """
    customer_id = get_or_create_stripe_customer(user, db)

    base_url = _get_base_url()
    s = _get_stripe()

    success_url = f"{base_url}{return_path}" if return_path else f"{base_url}/subscription/success"
    cancel_url = f"{base_url}{cancel_path}" if cancel_path else f"{base_url}/subscription/cancel"

    session = s.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": settings.stripe_pro_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"dealhawk_user_id": str(user.id)},
        # Stripe-level guard: only allow one active subscription per customer
        subscription_data={"metadata": {"dealhawk_user_id": str(user.id)}},
    )
    return session.url


def create_portal_session(
    user: User,
    db: Session,
    return_path: str | None = None,
) -> str:
    """Create a Stripe Billing Portal session and return the URL.

    Optional return_path overrides the default return URL.
    """
    customer_id = get_or_create_stripe_customer(user, db)

    base_url = _get_base_url()
    s = _get_stripe()

    return_url = f"{base_url}{return_path}" if return_path else f"{base_url}/subscription/success"

    session = s.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    """Verify and parse a Stripe webhook event."""
    s = _get_stripe()
    event = s.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )
    return event


def process_checkout_completed(event_data: dict, db: Session) -> None:
    """Handle checkout.session.completed — activate Pro subscription.

    Cross-references metadata.dealhawk_user_id with the customer lookup
    to prevent mismatched activations.
    """
    customer_id = event_data.get("customer")
    subscription_id = event_data.get("subscription")
    metadata = event_data.get("metadata", {})
    metadata_user_id = metadata.get("dealhawk_user_id")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning("Checkout completed for unknown customer: %s", customer_id)
        return

    # Cross-reference: metadata user ID must match the DB user
    if metadata_user_id and str(user.id) != metadata_user_id:
        logger.error(
            "Checkout metadata mismatch: customer %s maps to user %s but metadata says %s",
            customer_id, user.id, metadata_user_id,
        )
        return

    user.subscription_tier = "pro"
    user.subscription_status = "active"
    user.subscription_stripe_id = subscription_id
    db.commit()
    logger.info("User %s upgraded to Pro (sub: %s)", user.id, subscription_id)


def process_subscription_updated(event_data: dict, db: Session) -> None:
    """Handle customer.subscription.updated — sync status and tier."""
    customer_id = event_data.get("customer")
    raw_status = event_data.get("status", "")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    # Map to known statuses only — never store arbitrary strings
    mapped_status = _STATUS_MAP.get(raw_status, "expired")
    user.subscription_status = mapped_status

    # Sync tier based on status: active/past_due = pro, everything else = free
    if mapped_status in ("active", "past_due"):
        user.subscription_tier = "pro"
    else:
        user.subscription_tier = "free"

    current_period_end = event_data.get("current_period_end")
    if current_period_end:
        user.subscription_current_period_end = datetime.fromtimestamp(
            current_period_end, tz=timezone.utc
        ).replace(tzinfo=None)

    db.commit()
    logger.info("User %s subscription updated: %s -> %s", user.id, raw_status, mapped_status)


def process_subscription_deleted(event_data: dict, db: Session) -> None:
    """Handle customer.subscription.deleted — downgrade to free."""
    customer_id = event_data.get("customer")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.subscription_tier = "free"
    user.subscription_status = "canceled"
    user.subscription_stripe_id = None
    db.commit()
    logger.info("User %s subscription deleted, downgraded to free", user.id)


def process_invoice_payment_failed(event_data: dict, db: Session) -> None:
    """Handle invoice.payment_failed — mark subscription as past_due."""
    customer_id = event_data.get("customer")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.subscription_status = "past_due"
    db.commit()
    logger.info("User %s payment failed, marked as past_due", user.id)
