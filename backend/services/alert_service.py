"""Alert matching service: checks scored listings against user's active deal alerts."""

from sqlalchemy.orm import Session

from backend.database.models import DealAlert


def check_alerts_for_listing(
    user_id: int,
    make: str | None,
    model: str | None,
    year: int | None,
    asking_price: float | None,
    deal_score: int | None,
    days_on_lot: int | None,
    db: Session,
) -> list[dict]:
    """Check a scored listing against all of a user's active alerts.

    Returns a list of matching alert dicts (id, name).
    """
    alerts = (
        db.query(DealAlert)
        .filter(DealAlert.user_id == user_id, DealAlert.is_active == True)
        .all()
    )

    matches = []
    for alert in alerts:
        if _alert_matches(alert, make, model, year, asking_price, deal_score, days_on_lot):
            matches.append({"id": alert.id, "name": alert.name})

    return matches


def _alert_matches(
    alert: DealAlert,
    make: str | None,
    model: str | None,
    year: int | None,
    asking_price: float | None,
    deal_score: int | None,
    days_on_lot: int | None,
) -> bool:
    """Check if a single alert's criteria match the listing data.

    When the alert specifies a criterion but the listing lacks that data,
    treat it as a non-match (not a wildcard pass).
    """
    if alert.make is not None:
        if not make or alert.make.lower() != make.lower():
            return False

    if alert.model is not None:
        if not model or alert.model.lower() not in model.lower():
            return False

    if alert.year_min is not None:
        if year is None or year < alert.year_min:
            return False

    if alert.year_max is not None:
        if year is None or year > alert.year_max:
            return False

    if alert.price_max is not None:
        if asking_price is None or asking_price > alert.price_max:
            return False

    if alert.score_min is not None:
        if deal_score is None or deal_score < alert.score_min:
            return False

    if alert.days_on_lot_min is not None:
        if days_on_lot is None or days_on_lot < alert.days_on_lot_min:
            return False

    return True
