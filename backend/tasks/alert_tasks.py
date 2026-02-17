"""Celery tasks for deal alert matching and email notifications."""

import logging
import os

from jinja2 import Environment, FileSystemLoader

from backend.celery_app import app
from backend.database.db import SessionLocal
from backend.database.models import DealAlert, User
from backend.services.alert_service import _alert_matches
from backend.services.email_service import send_email, EmailSendError

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "email")
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=True,
)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def check_and_notify_alerts(self, listing_data: dict):
    """Check all active alerts against a scored listing and dispatch email tasks."""
    db = SessionLocal()
    try:
        alerts = db.query(DealAlert).filter(DealAlert.is_active == True).all()
        match_count = 0
        for alert in alerts:
            if _alert_matches(
                alert,
                make=listing_data.get("make"),
                model=listing_data.get("model"),
                year=listing_data.get("year"),
                asking_price=listing_data.get("asking_price"),
                deal_score=listing_data.get("deal_score"),
                days_on_lot=listing_data.get("days_on_lot"),
            ):
                user = db.query(User).filter(User.id == alert.user_id).first()
                if user and user.email:
                    send_alert_email.delay(
                        user_email=user.email,
                        alert_name=alert.name,
                        listing_data=listing_data,
                    )
                    match_count += 1

        logger.info("Alert check complete: %d matches from %d alerts", match_count, len(alerts))
        return {"matches": match_count, "total_alerts": len(alerts)}
    except Exception as exc:
        logger.exception("Alert check task failed")
        raise self.retry(exc=exc)
    finally:
        db.close()


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def send_alert_email(self, user_email: str, alert_name: str, listing_data: dict):
    """Render and send a deal alert notification email."""
    try:
        template = _jinja_env.get_template("alert_match.html")
        html_body = template.render(
            alert_name=alert_name,
            year=listing_data.get("year", ""),
            make=listing_data.get("make", ""),
            model=listing_data.get("model", ""),
            asking_price=listing_data.get("asking_price", 0),
            deal_score=listing_data.get("deal_score"),
            days_on_lot=listing_data.get("days_on_lot"),
            dealer_name=listing_data.get("dealer_name", ""),
        )

        subject = f"DealHawk Alert: {listing_data.get('year', '')} {listing_data.get('make', '')} {listing_data.get('model', '')} matches \"{alert_name}\""
        text_body = (
            f"Your alert \"{alert_name}\" matched a listing:\n\n"
            f"{listing_data.get('year', '')} {listing_data.get('make', '')} {listing_data.get('model', '')}\n"
            f"Price: ${listing_data.get('asking_price', 0):,.0f}\n"
            f"Score: {listing_data.get('deal_score', 'N/A')}\n"
        )

        send_email(user_email, subject, html_body, text_body)
        logger.info("Alert email sent to %s for alert '%s'", user_email, alert_name)
        return {"status": "sent", "to": user_email, "alert": alert_name}
    except EmailSendError as exc:
        logger.exception("Alert email failed to %s for '%s'", user_email, alert_name)
        raise self.retry(exc=exc)
