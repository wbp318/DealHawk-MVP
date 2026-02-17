"""Subscription endpoints: checkout, portal, status, success/cancel pages."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import User
from backend.api.auth import get_current_user_required
from backend.services.stripe_service import (
    create_checkout_session,
    create_portal_session,
)

subscription_router = APIRouter(prefix="/subscription", tags=["subscription"])

# CSP + security headers for static HTML pages
_HTML_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionStatusResponse(BaseModel):
    tier: str
    status: str
    current_period_end: str | None


@subscription_router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session for Pro subscription."""
    tier = current_user.subscription_tier or "free"
    sub_status = current_user.subscription_status or "active"

    # Block if already Pro and active
    if tier == "pro" and sub_status == "active":
        raise HTTPException(status_code=409, detail="Already subscribed to Pro")

    # Redirect past_due users to billing portal instead of creating new checkout
    if tier == "pro" and sub_status == "past_due":
        raise HTTPException(
            status_code=409,
            detail="Subscription is past due — use the billing portal to update payment",
        )

    try:
        url = create_checkout_session(current_user, db)
    except Exception:
        raise HTTPException(status_code=502, detail="Payment service unavailable")

    return CheckoutResponse(checkout_url=url)


@subscription_router.post("/portal", response_model=PortalResponse)
def portal(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Create a Stripe Billing Portal session for managing subscription."""
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    try:
        url = create_portal_session(current_user, db)
    except Exception:
        raise HTTPException(status_code=502, detail="Payment service unavailable")

    return PortalResponse(portal_url=url)


@subscription_router.get("/status", response_model=SubscriptionStatusResponse)
def status(current_user: User = Depends(get_current_user_required)):
    """Return the current user's subscription tier and status."""
    return SubscriptionStatusResponse(
        tier=current_user.subscription_tier or "free",
        status=current_user.subscription_status or "active",
        current_period_end=(
            str(current_user.subscription_current_period_end)
            if current_user.subscription_current_period_end
            else None
        ),
    )


@subscription_router.get("/success", response_class=HTMLResponse)
def subscription_success():
    """Simple HTML page shown after successful Stripe checkout."""
    return HTMLResponse(
        content="""<!DOCTYPE html>
<html><head><title>DealHawk Pro</title>
<style>body{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f0fdf4;margin:0}
.card{text-align:center;background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
h1{color:#16a34a;margin-bottom:8px}p{color:#64748b}</style></head>
<body><div class="card"><h1>Subscription Activated!</h1>
<p>You now have DealHawk Pro. Return to the extension to access saved vehicles and deal alerts.</p>
<p>You can close this tab.</p></div></body></html>""",
        headers=_HTML_HEADERS,
    )


@subscription_router.get("/cancel", response_class=HTMLResponse)
def subscription_cancel():
    """Simple HTML page shown when user cancels Stripe checkout."""
    return HTMLResponse(
        content="""<!DOCTYPE html>
<html><head><title>DealHawk</title>
<style>body{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f8f9fa;margin:0}
.card{text-align:center;background:#fff;padding:40px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
h1{color:#64748b;margin-bottom:8px}p{color:#94a3b8}</style></head>
<body><div class="card"><h1>Checkout Canceled</h1>
<p>No charges were made. Return to the DealHawk extension to try again anytime.</p>
<p>You can close this tab.</p></div></body></html>""",
        headers=_HTML_HEADERS,
    )
