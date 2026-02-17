"""Dealer API tier endpoints — API key auth, bulk scoring, market intel, inventory analysis."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from backend.api.dealer_auth import get_dealership_required
from backend.database.db import get_db
from backend.database.models import Dealership, IncentiveProgram
from backend.services.deal_scorer import score_deal, CARRYING_COST_PER_DAY
from backend.services.marketcheck_service import get_market_trends

dealer_router = APIRouter(prefix="/dealer", tags=["dealer"])


# --- Request models ---

class BulkVehicle(BaseModel):
    vin: str | None = Field(None, max_length=17)
    asking_price: float = Field(..., gt=0, le=500000)
    msrp: float = Field(..., gt=0, le=500000)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1980, le=2030)
    trim: str | None = Field(None, max_length=100)
    days_on_lot: int = Field(0, ge=0, le=3650)
    dealer_cash: float = Field(0, ge=0, le=100000)
    rebates_available: float = Field(0, ge=0, le=100000)


class BulkScoreRequest(BaseModel):
    vehicles: list[BulkVehicle] = Field(..., min_length=1, max_length=50)


class InventoryVehicle(BaseModel):
    vin: str | None = Field(None, max_length=17)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1980, le=2030)
    days_on_lot: int = Field(0, ge=0, le=3650)
    asking_price: float = Field(0, ge=0, le=500000)
    msrp: float = Field(0, ge=0, le=500000)


class InventoryAnalysisRequest(BaseModel):
    vehicles: list[InventoryVehicle] = Field(..., min_length=1, max_length=100)


# --- Endpoints ---

@dealer_router.post("/score/bulk")
def bulk_score(
    req: BulkScoreRequest,
    dealer: Dealership = Depends(get_dealership_required),
):
    """Score up to 50 vehicles in a single request."""
    results = []
    for v in req.vehicles:
        result = score_deal(
            asking_price=v.asking_price,
            msrp=v.msrp,
            make=v.make,
            model=v.model,
            year=v.year,
            trim=v.trim,
            days_on_lot=v.days_on_lot,
            dealer_cash=v.dealer_cash,
            rebates_available=v.rebates_available,
        )
        result["vin"] = v.vin
        results.append(result)

    return {
        "dealer": dealer.name,
        "count": len(results),
        "results": results,
    }


@dealer_router.get("/market/{make}/{model}")
def dealer_market_trends(
    make: str = Path(..., min_length=1, max_length=50),
    model: str = Path(..., min_length=1, max_length=100),
    dealer: Dealership = Depends(get_dealership_required),
    db: Session = Depends(get_db),
):
    """Market trends for dealers (same data, higher rate limits)."""
    try:
        return get_market_trends(make, model, db)
    except Exception:
        logger.exception("Dealer market trends fetch failed for %s %s", make, model)
        raise HTTPException(status_code=502, detail="Market data service temporarily unavailable")


@dealer_router.get("/incentives/{make}")
def dealer_incentives(
    make: str = Path(..., min_length=1, max_length=50),
    model: str | None = Query(None, max_length=100),
    dealer: Dealership = Depends(get_dealership_required),
    db: Session = Depends(get_db),
):
    """Incentives lookup for dealers with optional model filter."""
    query = db.query(IncentiveProgram).filter(IncentiveProgram.make == make)
    if model:
        query = query.filter(IncentiveProgram.model == model)
    incentives = query.all()

    return [
        {
            "id": i.id,
            "make": i.make,
            "model": i.model,
            "year": i.year,
            "type": i.incentive_type,
            "name": i.name,
            "amount": i.amount,
            "apr_rate": i.apr_rate,
            "apr_months": i.apr_months,
            "region": i.region,
            "start_date": str(i.start_date) if i.start_date else None,
            "end_date": str(i.end_date) if i.end_date else None,
            "stackable": i.stackable,
            "notes": i.notes,
        }
        for i in incentives
    ]


@dealer_router.post("/inventory/analysis")
def inventory_analysis(
    req: InventoryAnalysisRequest,
    dealer: Dealership = Depends(get_dealership_required),
):
    """Analyze inventory age, carrying costs, and risk tiers."""
    vehicles_out = []
    total_carrying_cost = 0
    total_days = 0
    aged_count = 0

    for v in req.vehicles:
        carrying_cost = round(v.days_on_lot * CARRYING_COST_PER_DAY, 2)
        total_carrying_cost += carrying_cost
        total_days += v.days_on_lot

        if v.days_on_lot >= 180:
            risk_tier = "critical"
        elif v.days_on_lot >= 90:
            risk_tier = "high"
        elif v.days_on_lot >= 60:
            risk_tier = "moderate"
        else:
            risk_tier = "low"

        if v.days_on_lot >= 90:
            aged_count += 1

        vehicles_out.append({
            "vin": v.vin,
            "make": v.make,
            "model": v.model,
            "year": v.year,
            "days_on_lot": v.days_on_lot,
            "carrying_cost": carrying_cost,
            "risk_tier": risk_tier,
        })

    total_vehicles = len(req.vehicles)
    avg_days = round(total_days / total_vehicles, 1) if total_vehicles else 0
    aged_pct = round(aged_count / total_vehicles * 100, 1) if total_vehicles else 0

    return {
        "dealer": dealer.name,
        "summary": {
            "total_vehicles": total_vehicles,
            "aged_count": aged_count,
            "aged_pct": aged_pct,
            "total_carrying_cost": round(total_carrying_cost, 2),
            "avg_days_on_lot": avg_days,
        },
        "vehicles": vehicles_out,
    }
