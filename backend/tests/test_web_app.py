"""Tests for DealHawk web app — public tools, auth, pro features, SEO."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, AsyncMock

from backend.database.models import Base, User, SavedVehicle, DealAlert
from backend.services.auth_service import hash_password


TEST_PASSWORD = "testpass123"
TEST_EMAIL = "web@test.com"


@pytest.fixture
def test_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return TestSession


@pytest.fixture
def client(test_session):
    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def client_with_user(test_session):
    db = test_session()
    user = User(
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        display_name="Test User",
        is_active=True,
        subscription_tier="free",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


@pytest.fixture
def client_with_pro_user(test_session):
    db = test_session()
    user = User(
        email=TEST_EMAIL,
        hashed_password=hash_password(TEST_PASSWORD),
        display_name="Pro User",
        is_active=True,
        subscription_tier="pro",
        subscription_status="active",
    )
    db.add(user)
    db.commit()
    db.close()

    with patch("backend.database.db.SessionLocal", test_session):
        from backend.api.app import create_app
        app = create_app()
        yield TestClient(app)


def _login(client, email=TEST_EMAIL, password=TEST_PASSWORD):
    """Login and return cookies."""
    resp = client.post("/login", data={"email": email, "password": password}, follow_redirects=False)
    return resp.cookies


# --- Phase 1: Public pages ---


class TestPublicPages:

    def test_landing_page(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "DealHawk" in r.text
        assert "Deal Scorer" in r.text

    def test_score_form(self, client):
        r = client.get("/tools/score")
        assert r.status_code == 200
        assert "MSRP" in r.text

    def test_vin_form(self, client):
        r = client.get("/tools/vin")
        assert r.status_code == 200
        assert "VIN" in r.text

    def test_tax_form(self, client):
        r = client.get("/tools/tax")
        assert r.status_code == 200
        assert "Section 179" in r.text

    def test_market_form(self, client):
        r = client.get("/tools/market")
        assert r.status_code == 200
        assert "Market Data" in r.text

    def test_pricing_page(self, client):
        r = client.get("/pricing")
        assert r.status_code == 200
        assert "Free" in r.text
        assert "Pro" in r.text


# --- Phase 1: Tool form submissions ---


class TestToolSubmissions:

    def test_score_submit_valid(self, client):
        r = client.post("/tools/score", data={
            "asking_price": "55000",
            "msrp": "65000",
            "make": "Ram",
            "model": "2500",
            "year": "2025",
            "days_on_lot": "90",
            "dealer_cash": "0",
            "rebates": "2000",
            "trim": "Laramie",
        })
        assert r.status_code == 200
        assert "score-gauge" in r.text
        assert "Negotiation Targets" in r.text

    def test_score_submit_bad_price(self, client):
        r = client.post("/tools/score", data={
            "asking_price": "999999",
            "msrp": "65000",
            "make": "Ram",
            "model": "2500",
            "year": "2025",
            "days_on_lot": "0",
            "dealer_cash": "0",
            "rebates": "0",
            "trim": "",
        })
        assert r.status_code == 200
        assert "error-box" in r.text

    def test_score_submit_bad_year(self, client):
        r = client.post("/tools/score", data={
            "asking_price": "55000",
            "msrp": "65000",
            "make": "Ram",
            "model": "2500",
            "year": "1900",
            "days_on_lot": "0",
            "dealer_cash": "0",
            "rebates": "0",
            "trim": "",
        })
        assert r.status_code == 200
        assert "error-box" in r.text

    def test_vin_submit_valid(self, client):
        mock_result = {
            "vin": "3C6UR5DL1PG600001",
            "year": 2023,
            "make": "Ram",
            "model": "2500",
            "trim": "Laramie",
            "body_class": "Pickup",
            "drive_type": "4WD",
            "engine_cylinders": 8,
            "engine_displacement": 6.4,
            "engine_type": None,
            "fuel_type": "Gasoline",
            "gvwr": "10000",
            "manufacturer": "FCA US LLC",
            "plant_city": "Saltillo",
            "plant_state": None,
            "plant_country": "Mexico",
        }
        with patch("backend.api.web_app.decode_vin", new_callable=AsyncMock, return_value=mock_result):
            r = client.post("/tools/vin", data={"vin": "3C6UR5DL1PG600001"})
        assert r.status_code == 200
        assert "Ram" in r.text
        assert "2500" in r.text

    def test_vin_submit_bad_vin(self, client):
        r = client.post("/tools/vin", data={"vin": "TOOSHORT"})
        assert r.status_code == 200
        assert "error-box" in r.text
        assert "17 characters" in r.text

    def test_vin_submit_invalid_chars(self, client):
        r = client.post("/tools/vin", data={"vin": "3C6UR5DL1OG600001"})  # O is invalid
        assert r.status_code == 200
        assert "error-box" in r.text

    def test_tax_submit_valid(self, client):
        r = client.post("/tools/tax", data={
            "vehicle_price": "65000",
            "business_use_pct": "100",
            "tax_bracket": "24",
            "state_tax_rate": "5",
            "model": "Ram 2500",
            "gvwr_override": "0",
            "down_payment": "0",
            "loan_interest_rate": "0",
            "loan_term_months": "60",
        })
        assert r.status_code == 200
        assert "Qualifies" in r.text

    def test_tax_submit_low_business_use(self, client):
        r = client.post("/tools/tax", data={
            "vehicle_price": "65000",
            "business_use_pct": "40",
            "tax_bracket": "24",
            "state_tax_rate": "0",
            "model": "",
            "gvwr_override": "0",
            "down_payment": "0",
            "loan_interest_rate": "0",
            "loan_term_months": "60",
        })
        assert r.status_code == 200
        assert "Does Not Qualify" in r.text

    def test_tax_submit_bad_price(self, client):
        r = client.post("/tools/tax", data={
            "vehicle_price": "-100",
            "business_use_pct": "100",
            "tax_bracket": "24",
            "state_tax_rate": "0",
            "model": "",
            "gvwr_override": "0",
            "down_payment": "0",
            "loan_interest_rate": "0",
            "loan_term_months": "60",
        })
        assert r.status_code == 200
        assert "error-box" in r.text

    def test_market_submit_valid(self, client):
        r = client.post("/tools/market", data={"make": "Ram", "model": "2500"})
        assert r.status_code == 200
        assert "Days Supply" in r.text or "Market Overview" in r.text

    def test_market_submit_empty_make(self, client):
        r = client.post("/tools/market", data={"make": "", "model": "2500"})
        assert r.status_code == 200
        assert "error-box" in r.text


# --- Phase 2: Auth ---


class TestAuth:

    def test_login_page(self, client):
        r = client.get("/login")
        assert r.status_code == 200
        assert "Sign in" in r.text

    def test_register_page(self, client):
        r = client.get("/register")
        assert r.status_code == 200
        assert "Create" in r.text

    def test_register_and_auto_login(self, client):
        r = client.post("/register", data={
            "email": "new@test.com",
            "password": "testpass123",
            "display_name": "New User",
        }, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/account"
        assert "dh_web_session" in r.cookies

    def test_register_short_password(self, client):
        r = client.post("/register", data={
            "email": "new@test.com",
            "password": "short",
            "display_name": "",
        })
        assert r.status_code == 400
        assert "8 characters" in r.text

    def test_register_duplicate_email(self, client_with_user):
        r = client_with_user.post("/register", data={
            "email": TEST_EMAIL,
            "password": "testpass123",
            "display_name": "",
        })
        assert r.status_code == 409
        assert "already exists" in r.text

    def test_login_success(self, client_with_user):
        r = client_with_user.post("/login", data={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        }, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/account"
        assert "dh_web_session" in r.cookies

    def test_login_wrong_password(self, client_with_user):
        r = client_with_user.post("/login", data={
            "email": TEST_EMAIL,
            "password": "wrongpassword",
        })
        assert r.status_code == 401
        assert "Invalid email or password" in r.text

    def test_login_redirects_if_logged_in(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/login", cookies=cookies, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/account"

    def test_account_requires_login(self, client):
        r = client.get("/account", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_account_renders_with_session(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/account", cookies=cookies)
        assert r.status_code == 200
        assert "Test User" in r.text

    def test_logout_clears_cookie(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/logout", cookies=cookies, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_nav_shows_sign_in_when_logged_out(self, client):
        r = client.get("/")
        assert "Sign In" in r.text

    def test_nav_shows_account_when_logged_in(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/", cookies=cookies)
        assert "Account" in r.text
        assert "Logout" in r.text


# --- Phase 3: Pro features ---


class TestProFeatures:

    def test_saved_page_requires_login(self, client):
        r = client.get("/account/saved", follow_redirects=False)
        assert r.status_code == 303

    def test_saved_page_shows_pro_gate(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/account/saved", cookies=cookies)
        assert r.status_code == 200
        assert "Pro Feature" in r.text
        assert "Upgrade" in r.text

    def test_saved_page_shows_form_for_pro(self, client_with_pro_user):
        cookies = _login(client_with_pro_user)
        r = client_with_pro_user.get("/account/saved", cookies=cookies)
        assert r.status_code == 200
        assert "Save a Vehicle" in r.text

    def test_save_vehicle_requires_pro(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.post("/account/saved", data={
            "vin": "3C6UR5DL1PG600001",
            "year": "2025", "make": "Ram", "model": "2500",
            "trim": "", "asking_price": "55000", "msrp": "65000",
            "days_on_lot": "0", "dealer_name": "", "deal_score": "0",
            "deal_grade": "", "notes": "",
        }, cookies=cookies)
        assert r.status_code == 403

    def test_save_and_delete_vehicle(self, client_with_pro_user):
        cookies = _login(client_with_pro_user)

        # Save
        r = client_with_pro_user.post("/account/saved", data={
            "vin": "3C6UR5DL1PG600001",
            "year": "2025", "make": "Ram", "model": "2500",
            "trim": "Laramie", "asking_price": "55000", "msrp": "65000",
            "days_on_lot": "90", "dealer_name": "Test Dealer", "deal_score": "75",
            "deal_grade": "B+", "notes": "Nice truck",
        }, cookies=cookies)
        assert r.status_code == 200
        assert "Ram" in r.text
        assert "2500" in r.text

        # Delete (vehicle ID = 1)
        r = client_with_pro_user.delete("/account/saved/1", cookies=cookies)
        assert r.status_code == 200
        assert "No saved vehicles" in r.text

    def test_alerts_page_shows_pro_gate(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/account/alerts", cookies=cookies)
        assert r.status_code == 200
        assert "Pro Feature" in r.text

    def test_create_and_delete_alert(self, client_with_pro_user):
        cookies = _login(client_with_pro_user)

        # Create
        r = client_with_pro_user.post("/account/alerts", data={
            "name": "Ram 2500 under 60k",
            "make": "Ram", "model": "2500",
            "year_min": "2024", "year_max": "2026",
            "price_max": "60000", "score_min": "50", "days_on_lot_min": "30",
        }, cookies=cookies)
        assert r.status_code == 200
        assert "Ram 2500 under 60k" in r.text
        assert "Active" in r.text

        # Toggle
        r = client_with_pro_user.patch("/account/alerts/1/toggle", cookies=cookies)
        assert r.status_code == 200
        assert "Paused" in r.text

        # Delete
        r = client_with_pro_user.delete("/account/alerts/1", cookies=cookies)
        assert r.status_code == 200
        assert "No alerts" in r.text

    def test_subscription_page(self, client_with_user):
        cookies = _login(client_with_user)
        r = client_with_user.get("/account/subscription", cookies=cookies)
        assert r.status_code == 200
        assert "Current Plan" in r.text
        assert "Upgrade" in r.text


# --- Phase 4: SEO ---


class TestSEO:

    def test_robots_txt(self, client):
        r = client.get("/robots.txt")
        assert r.status_code == 200
        assert "User-agent: *" in r.text
        assert "Sitemap" in r.text
        assert "/account" in r.text  # Disallowed

    def test_sitemap_xml(self, client):
        r = client.get("/sitemap.xml")
        assert r.status_code == 200
        assert "urlset" in r.text
        assert "/tools/score" in r.text
        assert "/tools/tax" in r.text

    def test_landing_has_meta_tags(self, client):
        r = client.get("/")
        assert "og:title" in r.text
        assert "og:description" in r.text

    def test_unique_titles(self, client):
        pages = ["/", "/tools/score", "/tools/vin", "/tools/tax", "/tools/market", "/pricing"]
        titles = set()
        for path in pages:
            r = client.get(path)
            # Extract title from <title>...</title>
            start = r.text.find("<title>") + 7
            end = r.text.find("</title>")
            title = r.text[start:end]
            titles.add(title)
        # All pages should have unique titles
        assert len(titles) == len(pages)

    def test_tax_page_has_seo_content(self, client):
        r = client.get("/tools/tax")
        assert "What Is Section 179" in r.text
        assert "GVWR Thresholds" in r.text
