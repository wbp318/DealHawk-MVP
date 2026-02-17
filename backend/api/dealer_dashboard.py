"""Dealer dashboard — server-rendered Jinja2 + HTMX views with session-based auth."""

import logging
import os
from datetime import date

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.db import get_db
from backend.database.models import Dealership
from backend.services.auth_service import verify_password
from backend.services.deal_scorer import CARRYING_COST_PER_DAY
from backend.services.marketcheck_service import get_market_trends

logger = logging.getLogger(__name__)

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

_SESSION_COOKIE = "dh_dealer_session"
_SESSION_MAX_AGE = 86400  # 24 hours


def _get_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.jwt_secret_key)


def _get_dealer_from_session(request: Request, db: Session) -> Dealership | None:
    """Read signed session cookie and return the dealer, or None."""
    cookie = request.cookies.get(_SESSION_COOKIE)
    if not cookie:
        return None
    try:
        serializer = _get_serializer()
        dealer_id = serializer.loads(cookie, max_age=_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    dealer = db.query(Dealership).filter(
        Dealership.id == dealer_id,
        Dealership.is_active == True,
    ).first()
    return dealer


def get_dealer_required(request: Request, db: Session = Depends(get_db)) -> Dealership:
    """FastAPI dependency — redirects to login if no valid session."""
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        raise _redirect_to_login()
    return dealer


def _redirect_to_login():
    """Return an HTTPException-like redirect (use raise)."""
    from fastapi import HTTPException
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url="/dashboard/login", status_code=303)
    raise HTTPException(status_code=303, headers={"Location": "/dashboard/login"})


# --- Routes ---

@dashboard_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("dealer/login.html", {
        "request": request,
        "error": error,
    })


@dashboard_router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    dealer = db.query(Dealership).filter(
        Dealership.email == email,
        Dealership.is_active == True,
    ).first()

    if not dealer or not dealer.hashed_password:
        return templates.TemplateResponse("dealer/login.html", {
            "request": request,
            "error": "Invalid email or password",
        }, status_code=401)

    if not verify_password(password, dealer.hashed_password):
        return templates.TemplateResponse("dealer/login.html", {
            "request": request,
            "error": "Invalid email or password",
        }, status_code=401)

    serializer = _get_serializer()
    token = serializer.dumps(dealer.id)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@dashboard_router.get("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/dashboard/login", status_code=303)
    response.delete_cookie(_SESSION_COOKIE)
    return response


@dashboard_router.get("", response_class=HTMLResponse)
def dashboard_overview(
    request: Request,
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return RedirectResponse(url="/dashboard/login", status_code=303)

    # Reset counters if date changed
    today = date.today()
    if dealer.last_request_date != today:
        requests_today = 0
    else:
        requests_today = dealer.requests_today

    current_month = today.strftime("%Y-%m")
    if dealer.last_request_month != current_month:
        requests_this_month = 0
    else:
        requests_this_month = dealer.requests_this_month

    return templates.TemplateResponse("dealer/dashboard.html", {
        "request": request,
        "dealer": dealer,
        "requests_today": requests_today,
        "requests_this_month": requests_this_month,
    })


@dashboard_router.get("/inventory", response_class=HTMLResponse)
def inventory_page(
    request: Request,
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return RedirectResponse(url="/dashboard/login", status_code=303)

    return templates.TemplateResponse("dealer/inventory.html", {
        "request": request,
        "dealer": dealer,
    })


@dashboard_router.get("/market", response_class=HTMLResponse)
def market_page(
    request: Request,
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return RedirectResponse(url="/dashboard/login", status_code=303)

    return templates.TemplateResponse("dealer/market.html", {
        "request": request,
        "dealer": dealer,
    })


@dashboard_router.get("/usage", response_class=HTMLResponse)
def usage_page(
    request: Request,
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return RedirectResponse(url="/dashboard/login", status_code=303)

    today = date.today()
    requests_today = dealer.requests_today if dealer.last_request_date == today else 0
    current_month = today.strftime("%Y-%m")
    requests_this_month = dealer.requests_this_month if dealer.last_request_month == current_month else 0

    return templates.TemplateResponse("dealer/usage.html", {
        "request": request,
        "dealer": dealer,
        "requests_today": requests_today,
        "requests_this_month": requests_this_month,
    })


# --- HTMX Partials ---

@dashboard_router.get("/partials/usage", response_class=HTMLResponse)
def usage_partial(
    request: Request,
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return HTMLResponse("<p>Session expired</p>", status_code=401)

    today = date.today()
    requests_today = dealer.requests_today if dealer.last_request_date == today else 0
    current_month = today.strftime("%Y-%m")
    requests_this_month = dealer.requests_this_month if dealer.last_request_month == current_month else 0

    return templates.TemplateResponse("dealer/_usage.html", {
        "request": request,
        "dealer": dealer,
        "requests_today": requests_today,
        "requests_this_month": requests_this_month,
    })


@dashboard_router.post("/partials/inventory-results", response_class=HTMLResponse)
def inventory_results_partial(
    request: Request,
    vins_text: str = Form(""),
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return HTMLResponse("<p>Session expired</p>", status_code=401)

    # Parse VINs from textarea (one per line)
    lines = [line.strip() for line in vins_text.strip().split("\n") if line.strip()]
    if not lines:
        return HTMLResponse("<p>No VINs provided.</p>")

    # Simple inventory analysis based on VIN count
    vehicles = []
    for vin in lines[:100]:  # Cap at 100
        vehicles.append({
            "vin": vin,
            "status": "submitted",
        })

    return templates.TemplateResponse("dealer/_inventory.html", {
        "request": request,
        "vehicles": vehicles,
        "count": len(vehicles),
    })


@dashboard_router.post("/partials/market-results", response_class=HTMLResponse)
def market_results_partial(
    request: Request,
    make: str = Form(""),
    model: str = Form(""),
    db: Session = Depends(get_db),
):
    dealer = _get_dealer_from_session(request, db)
    if dealer is None:
        return HTMLResponse("<p>Session expired</p>", status_code=401)

    if not make or not model:
        return HTMLResponse("<p>Please enter both make and model.</p>")

    try:
        trends = get_market_trends(make, model, db)
    except Exception:
        logger.exception("Market trends fetch failed in dashboard for %s %s", make, model)
        trends = {"error": True}

    return templates.TemplateResponse("dealer/_market.html", {
        "request": request,
        "trends": trends,
        "make": make,
        "model": model,
    })
