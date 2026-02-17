"""Deal alert CRUD endpoints + on-demand matching — all require authentication."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import DealAlert, User
from backend.api.auth import get_current_user_required
from backend.services.alert_service import check_alerts_for_listing

alert_router = APIRouter(prefix="/alerts", tags=["alerts"])


# --- Request/Response Models ---

class CreateAlertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    make: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=100)
    year_min: int | None = Field(None, ge=1980, le=2030)
    year_max: int | None = Field(None, ge=1980, le=2030)
    price_max: float | None = Field(None, gt=0, le=500000)
    score_min: int | None = Field(None, ge=0, le=100)
    days_on_lot_min: int | None = Field(None, ge=0, le=3650)

    @model_validator(mode="after")
    def check_year_range(self):
        if self.year_min is not None and self.year_max is not None:
            if self.year_min > self.year_max:
                raise ValueError("year_min must be <= year_max")
        return self


class UpdateAlertRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    make: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=100)
    year_min: int | None = Field(None, ge=1980, le=2030)
    year_max: int | None = Field(None, ge=1980, le=2030)
    price_max: float | None = Field(None, gt=0, le=500000)
    score_min: int | None = Field(None, ge=0, le=100)
    days_on_lot_min: int | None = Field(None, ge=0, le=3650)
    is_active: bool | None = None


class CheckAlertsRequest(BaseModel):
    make: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=100)
    year: int | None = Field(None, ge=1980, le=2030)
    asking_price: float | None = Field(None, gt=0, le=500000)
    deal_score: int | None = Field(None, ge=0, le=100)
    days_on_lot: int | None = Field(None, ge=0, le=3650)


class AlertResponse(BaseModel):
    id: int
    name: str
    make: str | None
    model: str | None
    year_min: int | None
    year_max: int | None
    price_max: float | None
    score_min: int | None
    days_on_lot_min: int | None
    is_active: bool
    created_at: str


# --- Endpoints ---

@alert_router.get("/", response_model=list[AlertResponse])
def list_alerts(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """List all deal alerts for the current user."""
    alerts = (
        db.query(DealAlert)
        .filter(DealAlert.user_id == current_user.id)
        .order_by(DealAlert.created_at.desc())
        .all()
    )
    return [_to_response(a) for a in alerts]


@alert_router.post("/", response_model=AlertResponse, status_code=201)
def create_alert(
    req: CreateAlertRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Create a new deal alert."""
    alert = DealAlert(
        user_id=current_user.id,
        name=req.name,
        make=req.make,
        model=req.model,
        year_min=req.year_min,
        year_max=req.year_max,
        price_max=req.price_max,
        score_min=req.score_min,
        days_on_lot_min=req.days_on_lot_min,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _to_response(alert)


@alert_router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Get a single deal alert by ID."""
    alert = _get_user_alert(alert_id, current_user.id, db)
    return _to_response(alert)


@alert_router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert(
    alert_id: int,
    req: UpdateAlertRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Update a deal alert's criteria or active status."""
    alert = _get_user_alert(alert_id, current_user.id, db)
    update_data = req.model_dump(exclude_unset=True)
    if "name" in update_data and not update_data["name"]:
        raise HTTPException(status_code=422, detail="Alert name cannot be empty")
    if "year_min" in update_data and "year_max" in update_data:
        y_min = update_data.get("year_min") or alert.year_min
        y_max = update_data.get("year_max") or alert.year_max
        if y_min is not None and y_max is not None and y_min > y_max:
            raise HTTPException(status_code=422, detail="year_min must be <= year_max")
    for key, value in update_data.items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    return _to_response(alert)


@alert_router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Delete a deal alert."""
    alert = _get_user_alert(alert_id, current_user.id, db)
    db.delete(alert)
    db.commit()
    return {"deleted": True}


@alert_router.post("/check")
def check_alerts(
    req: CheckAlertsRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Check a listing against the user's active alerts. Returns matching alerts."""
    matches = check_alerts_for_listing(
        user_id=current_user.id,
        make=req.make,
        model=req.model,
        year=req.year,
        asking_price=req.asking_price,
        deal_score=req.deal_score,
        days_on_lot=req.days_on_lot,
        db=db,
    )
    return {"matches": matches, "count": len(matches)}


# --- Helpers ---

def _get_user_alert(alert_id: int, user_id: int, db: Session) -> DealAlert:
    alert = db.query(DealAlert).filter(
        DealAlert.id == alert_id,
        DealAlert.user_id == user_id,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Deal alert not found")
    return alert


def _to_response(a: DealAlert) -> AlertResponse:
    return AlertResponse(
        id=a.id,
        name=a.name,
        make=a.make,
        model=a.model,
        year_min=a.year_min,
        year_max=a.year_max,
        price_max=a.price_max,
        score_min=a.score_min,
        days_on_lot_min=a.days_on_lot_min,
        is_active=a.is_active,
        created_at=str(a.created_at),
    )
