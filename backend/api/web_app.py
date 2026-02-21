"""DealHawk public web app — server-rendered Jinja2 + HTMX views."""

import logging
import os
import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.database.db import get_db
from backend.database.models import User, SavedVehicle, DealAlert
from backend.services.auth_service import (
    authenticate_user,
    register_user,
    DuplicateEmailError,
)
from backend.services.deal_scorer import score_deal
from backend.services.marketcheck_service import get_market_trends, get_market_stats
from backend.services.section179_service import calculate_section_179
from backend.services.vin_decoder import decode_vin
from backend.services.stripe_service import create_checkout_session, create_portal_session

from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

web_router = APIRouter(tags=["web"])

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

# --- Session auth (consumer) ---

_SESSION_COOKIE = "dh_web_session"
_SESSION_MAX_AGE = 604800  # 7 days


def _get_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.jwt_secret_key + "-web")


def _get_user_from_session(request: Request, db: Session) -> User | None:
    """Read signed session cookie and return the user, or None."""
    cookie = request.cookies.get(_SESSION_COOKIE)
    if not cookie:
        return None
    try:
        serializer = _get_serializer()
        user_id = serializer.loads(cookie, max_age=_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def _set_session_cookie(response, user_id: int):
    """Set signed session cookie on response."""
    serializer = _get_serializer()
    token = serializer.dumps(user_id)
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


# --- Input validation ---

def _validate_score_input(
    asking_price: float,
    msrp: float,
    year: int,
    days_on_lot: int,
) -> str | None:
    """Return error message or None if valid."""
    if asking_price <= 0 or asking_price > 500000:
        return "Asking price must be between $1 and $500,000"
    if msrp <= 0 or msrp > 500000:
        return "MSRP must be between $1 and $500,000"
    if year < 1980 or year > 2030:
        return "Year must be between 1980 and 2030"
    if days_on_lot < 0 or days_on_lot > 3650:
        return "Days on lot must be between 0 and 3,650"
    return None


def _validate_vin(vin: str) -> str | None:
    """Return error message or None if valid."""
    vin = vin.strip().upper()
    if len(vin) != 17:
        return "VIN must be exactly 17 characters"
    if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin):
        return "VIN contains invalid characters (I, O, Q not allowed)"
    return None


def _validate_tax_input(
    vehicle_price: float,
    business_use_pct: float,
    tax_bracket: float,
) -> str | None:
    """Return error message or None if valid."""
    if vehicle_price <= 0 or vehicle_price > 500000:
        return "Vehicle price must be between $1 and $500,000"
    if business_use_pct < 0 or business_use_pct > 100:
        return "Business use must be between 0% and 100%"
    if tax_bracket < 0 or tax_bracket > 50:
        return "Tax bracket must be between 0% and 50%"
    return None


# --- Phase 1: Public tools ---


@web_router.get("/", response_class=HTMLResponse)
def landing_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    return templates.TemplateResponse("web/landing.html", {
        "request": request,
        "user": user,
        "active": "home",
    })


@web_router.get("/tools/score", response_class=HTMLResponse)
def score_form(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    return templates.TemplateResponse("web/tools/score.html", {
        "request": request,
        "user": user,
        "active": "score",
    })


@web_router.post("/tools/score", response_class=HTMLResponse)
def score_submit(
    request: Request,
    asking_price: float = Form(...),
    msrp: float = Form(...),
    make: str = Form(...),
    model: str = Form(...),
    year: int = Form(...),
    days_on_lot: int = Form(0),
    dealer_cash: float = Form(0),
    rebates: float = Form(0),
    trim: str = Form(""),
):
    error = _validate_score_input(asking_price, msrp, year, days_on_lot)
    if error:
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": error,
        })

    try:
        result = score_deal(
            asking_price=asking_price,
            msrp=msrp,
            make=make,
            model=model,
            year=year,
            days_on_lot=days_on_lot,
            dealer_cash=dealer_cash,
            rebates_available=rebates,
            trim=trim or None,
        )
    except Exception:
        logger.exception("Score deal failed")
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": "Something went wrong. Please check your inputs and try again.",
        })

    return templates.TemplateResponse("web/partials/_score_results.html", {
        "request": request,
        "result": result,
        "asking_price": asking_price,
        "msrp": msrp,
    })


@web_router.get("/tools/vin", response_class=HTMLResponse)
def vin_form(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    return templates.TemplateResponse("web/tools/vin.html", {
        "request": request,
        "user": user,
        "active": "vin",
    })


@web_router.post("/tools/vin", response_class=HTMLResponse)
async def vin_submit(
    request: Request,
    vin: str = Form(...),
    db: Session = Depends(get_db),
):
    vin = vin.strip().upper()
    error = _validate_vin(vin)
    if error:
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": error,
        })

    try:
        result = await decode_vin(vin, db)
    except ValueError as e:
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": str(e),
        })
    except Exception:
        logger.exception("VIN decode failed for %s", vin)
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": "Could not decode VIN. Please try again later.",
        })

    return templates.TemplateResponse("web/partials/_vin_results.html", {
        "request": request,
        "result": result,
    })


@web_router.get("/tools/tax", response_class=HTMLResponse)
def tax_form(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    return templates.TemplateResponse("web/tools/tax.html", {
        "request": request,
        "user": user,
        "active": "tax",
    })


@web_router.post("/tools/tax", response_class=HTMLResponse)
def tax_submit(
    request: Request,
    vehicle_price: float = Form(...),
    business_use_pct: float = Form(...),
    tax_bracket: float = Form(...),
    state_tax_rate: float = Form(0),
    model: str = Form(""),
    gvwr_override: int = Form(0),
    down_payment: float = Form(0),
    loan_interest_rate: float = Form(0),
    loan_term_months: int = Form(60),
):
    error = _validate_tax_input(vehicle_price, business_use_pct, tax_bracket)
    if error:
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": error,
        })

    try:
        result = calculate_section_179(
            vehicle_price=vehicle_price,
            business_use_pct=business_use_pct,
            tax_bracket=tax_bracket,
            state_tax_rate=state_tax_rate,
            model=model or None,
            gvwr_override=gvwr_override or None,
            down_payment=down_payment,
            loan_interest_rate=loan_interest_rate,
            loan_term_months=loan_term_months,
        )
    except Exception:
        logger.exception("Section 179 calculation failed")
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": "Calculation failed. Please check your inputs.",
        })

    return templates.TemplateResponse("web/partials/_tax_results.html", {
        "request": request,
        "result": result,
    })


@web_router.get("/tools/market", response_class=HTMLResponse)
def market_form(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    return templates.TemplateResponse("web/tools/market.html", {
        "request": request,
        "user": user,
        "active": "market",
    })


@web_router.post("/tools/market", response_class=HTMLResponse)
def market_submit(
    request: Request,
    make: str = Form(""),
    model: str = Form(""),
    db: Session = Depends(get_db),
):
    if not make.strip() or not model.strip():
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": "Please enter both make and model.",
        })

    make = make.strip()
    model = model.strip()

    try:
        trends = get_market_trends(make, model, db)
        stats = get_market_stats(make, model, db)
    except Exception:
        logger.exception("Market data fetch failed for %s %s", make, model)
        return templates.TemplateResponse("web/partials/_error.html", {
            "request": request,
            "error": "Could not fetch market data. Please try again later.",
        })

    return templates.TemplateResponse("web/partials/_market_results.html", {
        "request": request,
        "trends": trends,
        "stats": stats,
        "make": make,
        "model": model,
    })


@web_router.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    return templates.TemplateResponse("web/pricing.html", {
        "request": request,
        "user": user,
        "active": "pricing",
    })


# --- Phase 2: Auth ---


@web_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if user:
        return RedirectResponse(url="/account", status_code=303)
    return templates.TemplateResponse("web/login.html", {
        "request": request,
        "user": None,
        "active": "login",
    })


@web_router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(email, password, db)
    if not user:
        return templates.TemplateResponse("web/login.html", {
            "request": request,
            "user": None,
            "active": "login",
            "error": "Invalid email or password",
        }, status_code=401)

    response = RedirectResponse(url="/account", status_code=303)
    _set_session_cookie(response, user.id)
    return response


@web_router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if user:
        return RedirectResponse(url="/account", status_code=303)
    return templates.TemplateResponse("web/register.html", {
        "request": request,
        "user": None,
        "active": "register",
    })


@web_router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
    db: Session = Depends(get_db),
):
    if len(password) < 8:
        return templates.TemplateResponse("web/register.html", {
            "request": request,
            "user": None,
            "active": "register",
            "error": "Password must be at least 8 characters",
        }, status_code=400)

    try:
        user = register_user(email, password, display_name or None, db)
    except DuplicateEmailError:
        return templates.TemplateResponse("web/register.html", {
            "request": request,
            "user": None,
            "active": "register",
            "error": "An account with that email already exists",
        }, status_code=409)

    response = RedirectResponse(url="/account", status_code=303)
    _set_session_cookie(response, user.id)
    return response


@web_router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(_SESSION_COOKIE)
    return response


@web_router.get("/account", response_class=HTMLResponse)
def account_dashboard(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    saved_count = db.query(SavedVehicle).filter(SavedVehicle.user_id == user.id).count()
    alert_count = db.query(DealAlert).filter(DealAlert.user_id == user.id).count()

    return templates.TemplateResponse("web/account/dashboard.html", {
        "request": request,
        "user": user,
        "active": "account",
        "saved_count": saved_count,
        "alert_count": alert_count,
    })


# --- Phase 3: Pro features ---


@web_router.get("/account/saved", response_class=HTMLResponse)
def saved_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    is_pro = user.subscription_tier == "pro"
    vehicles = []
    if is_pro:
        vehicles = (
            db.query(SavedVehicle)
            .filter(SavedVehicle.user_id == user.id)
            .order_by(SavedVehicle.saved_at.desc())
            .all()
        )

    return templates.TemplateResponse("web/account/saved.html", {
        "request": request,
        "user": user,
        "active": "saved",
        "is_pro": is_pro,
        "vehicles": vehicles,
    })


@web_router.post("/account/saved", response_class=HTMLResponse)
def save_vehicle(
    request: Request,
    vin: str = Form(""),
    year: int = Form(0),
    make: str = Form(""),
    model: str = Form(""),
    trim: str = Form(""),
    asking_price: float = Form(0),
    msrp: float = Form(0),
    days_on_lot: int = Form(0),
    dealer_name: str = Form(""),
    deal_score: int = Form(0),
    deal_grade: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _get_user_from_session(request, db)
    if not user:
        return HTMLResponse("<p>Please log in</p>", status_code=401)
    if user.subscription_tier != "pro":
        return HTMLResponse("<p>Pro subscription required</p>", status_code=403)

    saved = SavedVehicle(
        user_id=user.id,
        vin=vin or None,
        year=year or None,
        make=make or None,
        model=model or None,
        trim=trim or None,
        asking_price=asking_price or None,
        msrp=msrp or None,
        days_on_lot=days_on_lot or None,
        dealer_name=dealer_name or None,
        deal_score=deal_score or None,
        deal_grade=deal_grade or None,
        notes=notes or None,
    )
    db.add(saved)
    db.commit()

    vehicles = (
        db.query(SavedVehicle)
        .filter(SavedVehicle.user_id == user.id)
        .order_by(SavedVehicle.saved_at.desc())
        .all()
    )
    return templates.TemplateResponse("web/partials/_saved_list.html", {
        "request": request,
        "vehicles": vehicles,
    })


@web_router.delete("/account/saved/{vehicle_id}", response_class=HTMLResponse)
def delete_saved_vehicle(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user_from_session(request, db)
    if not user:
        return HTMLResponse("<p>Please log in</p>", status_code=401)

    vehicle = db.query(SavedVehicle).filter(
        SavedVehicle.id == vehicle_id,
        SavedVehicle.user_id == user.id,
    ).first()
    if vehicle:
        db.delete(vehicle)
        db.commit()

    vehicles = (
        db.query(SavedVehicle)
        .filter(SavedVehicle.user_id == user.id)
        .order_by(SavedVehicle.saved_at.desc())
        .all()
    )
    return templates.TemplateResponse("web/partials/_saved_list.html", {
        "request": request,
        "vehicles": vehicles,
    })


@web_router.get("/account/alerts", response_class=HTMLResponse)
def alerts_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    is_pro = user.subscription_tier == "pro"
    alerts = []
    if is_pro:
        alerts = (
            db.query(DealAlert)
            .filter(DealAlert.user_id == user.id)
            .order_by(DealAlert.created_at.desc())
            .all()
        )

    return templates.TemplateResponse("web/account/alerts.html", {
        "request": request,
        "user": user,
        "active": "alerts",
        "is_pro": is_pro,
        "alerts": alerts,
    })


@web_router.post("/account/alerts", response_class=HTMLResponse)
def create_alert(
    request: Request,
    name: str = Form(...),
    make: str = Form(""),
    model: str = Form(""),
    year_min: int = Form(0),
    year_max: int = Form(0),
    price_max: float = Form(0),
    score_min: int = Form(0),
    days_on_lot_min: int = Form(0),
    db: Session = Depends(get_db),
):
    user = _get_user_from_session(request, db)
    if not user:
        return HTMLResponse("<p>Please log in</p>", status_code=401)
    if user.subscription_tier != "pro":
        return HTMLResponse("<p>Pro subscription required</p>", status_code=403)

    alert = DealAlert(
        user_id=user.id,
        name=name,
        make=make or None,
        model=model or None,
        year_min=year_min or None,
        year_max=year_max or None,
        price_max=price_max or None,
        score_min=score_min or None,
        days_on_lot_min=days_on_lot_min or None,
    )
    db.add(alert)
    db.commit()

    alerts = (
        db.query(DealAlert)
        .filter(DealAlert.user_id == user.id)
        .order_by(DealAlert.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("web/partials/_alert_list.html", {
        "request": request,
        "alerts": alerts,
    })


@web_router.delete("/account/alerts/{alert_id}", response_class=HTMLResponse)
def delete_alert(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user_from_session(request, db)
    if not user:
        return HTMLResponse("<p>Please log in</p>", status_code=401)

    alert = db.query(DealAlert).filter(
        DealAlert.id == alert_id,
        DealAlert.user_id == user.id,
    ).first()
    if alert:
        db.delete(alert)
        db.commit()

    alerts = (
        db.query(DealAlert)
        .filter(DealAlert.user_id == user.id)
        .order_by(DealAlert.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("web/partials/_alert_list.html", {
        "request": request,
        "alerts": alerts,
    })


@web_router.patch("/account/alerts/{alert_id}/toggle", response_class=HTMLResponse)
def toggle_alert(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _get_user_from_session(request, db)
    if not user:
        return HTMLResponse("<p>Please log in</p>", status_code=401)

    alert = db.query(DealAlert).filter(
        DealAlert.id == alert_id,
        DealAlert.user_id == user.id,
    ).first()
    if alert:
        alert.is_active = not alert.is_active
        db.commit()

    alerts = (
        db.query(DealAlert)
        .filter(DealAlert.user_id == user.id)
        .order_by(DealAlert.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("web/partials/_alert_list.html", {
        "request": request,
        "alerts": alerts,
    })


@web_router.get("/account/subscription", response_class=HTMLResponse)
def subscription_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    success = request.query_params.get("success")

    return templates.TemplateResponse("web/account/subscription.html", {
        "request": request,
        "user": user,
        "active": "subscription",
        "success": success,
    })


@web_router.post("/account/upgrade")
def upgrade_to_pro(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        checkout_url = create_checkout_session(user, db, return_path="/account/subscription?success=true")
    except Exception:
        logger.exception("Stripe checkout creation failed for user %s", user.id)
        return RedirectResponse(url="/account/subscription?error=checkout_failed", status_code=303)

    return RedirectResponse(url=checkout_url, status_code=303)


@web_router.post("/account/manage-billing")
def manage_billing(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    try:
        portal_url = create_portal_session(user, db, return_path="/account/subscription")
    except Exception:
        logger.exception("Stripe portal creation failed for user %s", user.id)
        return RedirectResponse(url="/account/subscription?error=portal_failed", status_code=303)

    return RedirectResponse(url=portal_url, status_code=303)


# --- Phase 4: SEO ---


@web_router.get("/robots.txt", response_class=HTMLResponse)
def robots_txt():
    settings = get_settings()
    base = settings.base_url or "http://localhost:8000"
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /account\n"
        "Disallow: /dashboard\n"
        f"\nSitemap: {base}/sitemap.xml\n"
    )
    return HTMLResponse(content=content, media_type="text/plain")


@web_router.get("/sitemap.xml", response_class=HTMLResponse)
def sitemap_xml():
    settings = get_settings()
    base = settings.base_url or "http://localhost:8000"
    today = date.today().isoformat()
    urls = [
        ("", "1.0", "weekly"),
        ("/tools/score", "0.9", "monthly"),
        ("/tools/vin", "0.9", "monthly"),
        ("/tools/tax", "0.9", "monthly"),
        ("/tools/market", "0.8", "monthly"),
        ("/pricing", "0.7", "monthly"),
    ]
    entries = "\n".join(
        f"  <url>\n"
        f"    <loc>{base}{path}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>"
        for path, priority, freq in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>"
    )
    return HTMLResponse(content=xml, media_type="application/xml")
