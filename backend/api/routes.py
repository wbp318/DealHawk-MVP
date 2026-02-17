from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import IncentiveProgram
from backend.services.vin_decoder import decode_vin
from backend.services.deal_scorer import score_deal
from backend.services.pricing_service import get_pricing
from backend.services.negotiation_service import generate_negotiation_brief
from backend.services.section179_service import calculate_section_179

router = APIRouter()


# --- Request/Response Models ---

class ScoreRequest(BaseModel):
    vin: str | None = Field(None, min_length=17, max_length=17, pattern=r'^[A-HJ-NPR-Z0-9]{17}$')
    asking_price: float = Field(..., gt=0, le=500000)
    msrp: float = Field(..., gt=0, le=500000)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1980, le=2030)
    trim: str | None = Field(None, max_length=100)
    days_on_lot: int = Field(0, ge=0, le=3650)
    dealer_cash: float = Field(0, ge=0, le=100000)
    rebates_available: float = Field(0, ge=0, le=100000)


class Section179Request(BaseModel):
    vehicle_price: float = Field(..., gt=0, le=500000)
    business_use_pct: float = Field(..., ge=0, le=100)
    tax_bracket: float = Field(..., ge=0, le=50)
    state_tax_rate: float = Field(0, ge=0, le=20)
    down_payment: float = Field(0, ge=0, le=500000)
    loan_interest_rate: float = Field(0, ge=0, le=30)
    loan_term_months: int = Field(60, ge=12, le=120)
    model: str | None = Field(None, max_length=100)
    gvwr: int | None = Field(None, ge=0, le=50000)


class NegotiationRequest(BaseModel):
    asking_price: float = Field(..., gt=0, le=500000)
    msrp: float = Field(..., gt=0, le=500000)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    year: int = Field(..., ge=1980, le=2030)
    trim: str | None = Field(None, max_length=100)
    days_on_lot: int = Field(0, ge=0, le=3650)
    rebates_available: float = Field(0, ge=0, le=100000)


# --- Endpoints ---

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "dealhawk", "version": "0.5.0"}


@router.get("/vin/{vin}")
async def decode_vin_endpoint(vin: str, db: Session = Depends(get_db)):
    """Decode a VIN using the NHTSA vPIC API and return enriched vehicle data."""
    try:
        result = await decode_vin(vin, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="VIN decode failed: upstream service unavailable")
    return result


@router.post("/score")
def score_listing(req: ScoreRequest):
    """Score a vehicle listing and return deal analysis with offer targets."""
    result = score_deal(
        asking_price=req.asking_price,
        msrp=req.msrp,
        make=req.make,
        model=req.model,
        year=req.year,
        trim=req.trim,
        days_on_lot=req.days_on_lot,
        dealer_cash=req.dealer_cash,
        rebates_available=req.rebates_available,
    )
    return result


@router.post("/negotiate")
def negotiate(req: NegotiationRequest, db: Session = Depends(get_db)):
    """Generate a full negotiation brief with talking points and offer targets."""
    pricing = get_pricing(
        year=req.year,
        make=req.make,
        model=req.model,
        msrp=req.msrp,
        trim=req.trim,
        db=db,
    )
    result = generate_negotiation_brief(
        asking_price=req.asking_price,
        msrp=req.msrp,
        invoice_price=pricing["invoice_price"],
        holdback=pricing["holdback"],
        true_dealer_cost=pricing["true_dealer_cost"],
        days_on_lot=req.days_on_lot,
        rebates_available=req.rebates_available,
        make=req.make,
        model=req.model,
        year=req.year,
    )
    return result


@router.get("/pricing/{year}/{make}/{model}")
def get_pricing_endpoint(
    year: int,
    make: str,
    model: str,
    msrp: float = 0,
    trim: str | None = None,
    db: Session = Depends(get_db),
):
    """Look up invoice, holdback, and true dealer cost for a vehicle."""
    if msrp <= 0:
        raise HTTPException(status_code=400, detail="msrp query parameter is required")
    result = get_pricing(year=year, make=make, model=model, msrp=msrp, trim=trim, db=db)
    return result


@router.get("/incentives/{make}")
def get_incentives(make: str, model: str | None = None, db: Session = Depends(get_db)):
    """Look up current manufacturer rebates and incentives."""
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


@router.post("/section-179/calculate")
def section_179_calculate(req: Section179Request):
    """Calculate Section 179 tax deduction for a business vehicle."""
    result = calculate_section_179(
        vehicle_price=req.vehicle_price,
        business_use_pct=req.business_use_pct,
        tax_bracket=req.tax_bracket,
        state_tax_rate=req.state_tax_rate,
        down_payment=req.down_payment,
        loan_interest_rate=req.loan_interest_rate,
        loan_term_months=req.loan_term_months,
        model=req.model,
        gvwr_override=req.gvwr,
    )
    return result
