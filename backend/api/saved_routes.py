"""Saved vehicle CRUD endpoints — all require authentication."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import SavedVehicle, User
from backend.api.auth import get_current_user_required

saved_router = APIRouter(prefix="/saved", tags=["saved"])


# --- Request/Response Models ---

class SaveVehicleRequest(BaseModel):
    vin: str | None = Field(None, max_length=17)
    platform: str | None = Field(None, max_length=50)
    listing_url: str | None = Field(None, max_length=2048)
    asking_price: float | None = Field(None, gt=0, le=500000)
    msrp: float | None = Field(None, gt=0, le=500000)
    year: int | None = Field(None, ge=1980, le=2030)
    make: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=100)
    trim: str | None = Field(None, max_length=100)
    days_on_lot: int | None = Field(None, ge=0, le=3650)
    dealer_name: str | None = Field(None, max_length=200)
    dealer_location: str | None = Field(None, max_length=200)
    deal_score: int | None = Field(None, ge=0, le=100)
    deal_grade: str | None = Field(None, max_length=10)
    notes: str | None = Field(None, max_length=5000)


class UpdateSavedVehicleRequest(BaseModel):
    notes: str | None = None
    asking_price: float | None = Field(None, gt=0, le=500000)
    days_on_lot: int | None = Field(None, ge=0, le=3650)
    deal_score: int | None = Field(None, ge=0, le=100)
    deal_grade: str | None = Field(None, max_length=10)


class SavedVehicleResponse(BaseModel):
    id: int
    vin: str | None
    platform: str | None
    listing_url: str | None
    asking_price: float | None
    msrp: float | None
    year: int | None
    make: str | None
    model: str | None
    trim: str | None
    days_on_lot: int | None
    dealer_name: str | None
    dealer_location: str | None
    deal_score: int | None
    deal_grade: str | None
    notes: str | None
    saved_at: str
    updated_at: str


# --- Endpoints ---

@saved_router.get("/", response_model=list[SavedVehicleResponse])
def list_saved(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """List all saved vehicles for the current user."""
    vehicles = (
        db.query(SavedVehicle)
        .filter(SavedVehicle.user_id == current_user.id)
        .order_by(SavedVehicle.saved_at.desc())
        .all()
    )
    return [_to_response(v) for v in vehicles]


@saved_router.post("/", response_model=SavedVehicleResponse, status_code=201)
def save_vehicle(
    req: SaveVehicleRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Save a vehicle listing snapshot."""
    vehicle = SavedVehicle(
        user_id=current_user.id,
        vin=req.vin,
        platform=req.platform,
        listing_url=req.listing_url,
        asking_price=req.asking_price,
        msrp=req.msrp,
        year=req.year,
        make=req.make,
        model=req.model,
        trim=req.trim,
        days_on_lot=req.days_on_lot,
        dealer_name=req.dealer_name,
        dealer_location=req.dealer_location,
        deal_score=req.deal_score,
        deal_grade=req.deal_grade,
        notes=req.notes,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return _to_response(vehicle)


@saved_router.get("/{vehicle_id}", response_model=SavedVehicleResponse)
def get_saved(
    vehicle_id: int,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Get a single saved vehicle by ID."""
    vehicle = _get_user_vehicle(vehicle_id, current_user.id, db)
    return _to_response(vehicle)


@saved_router.patch("/{vehicle_id}", response_model=SavedVehicleResponse)
def update_saved(
    vehicle_id: int,
    req: UpdateSavedVehicleRequest,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Update a saved vehicle's notes or score."""
    vehicle = _get_user_vehicle(vehicle_id, current_user.id, db)
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vehicle, key, value)
    db.commit()
    db.refresh(vehicle)
    return _to_response(vehicle)


@saved_router.delete("/{vehicle_id}")
def delete_saved(
    vehicle_id: int,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    """Delete a saved vehicle."""
    vehicle = _get_user_vehicle(vehicle_id, current_user.id, db)
    db.delete(vehicle)
    db.commit()
    return {"deleted": True}


# --- Helpers ---

def _get_user_vehicle(vehicle_id: int, user_id: int, db: Session) -> SavedVehicle:
    vehicle = db.query(SavedVehicle).filter(
        SavedVehicle.id == vehicle_id,
        SavedVehicle.user_id == user_id,
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Saved vehicle not found")
    return vehicle


def _to_response(v: SavedVehicle) -> SavedVehicleResponse:
    return SavedVehicleResponse(
        id=v.id,
        vin=v.vin,
        platform=v.platform,
        listing_url=v.listing_url,
        asking_price=v.asking_price,
        msrp=v.msrp,
        year=v.year,
        make=v.make,
        model=v.model,
        trim=v.trim,
        days_on_lot=v.days_on_lot,
        dealer_name=v.dealer_name,
        dealer_location=v.dealer_location,
        deal_score=v.deal_score,
        deal_grade=v.deal_grade,
        notes=v.notes,
        saved_at=str(v.saved_at),
        updated_at=str(v.updated_at),
    )
