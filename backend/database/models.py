from datetime import datetime, date
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Date, Text, Index, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """User account for saved vehicles and deal alerts."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Subscription (Phase 3)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")
    subscription_status: Mapped[str] = mapped_column(String(20), default="active")
    subscription_stripe_id: Mapped[str | None] = mapped_column(String(255))
    subscription_current_period_end: Mapped[datetime | None] = mapped_column(DateTime)


class Vehicle(Base):
    """Decoded vehicle data keyed by VIN."""
    __tablename__ = "vehicles"

    vin: Mapped[str] = mapped_column(String(17), primary_key=True)
    year: Mapped[int | None] = mapped_column(Integer)
    make: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    trim: Mapped[str | None] = mapped_column(String(100))
    body_class: Mapped[str | None] = mapped_column(String(100))
    drive_type: Mapped[str | None] = mapped_column(String(50))
    engine_cylinders: Mapped[int | None] = mapped_column(Integer)
    engine_displacement: Mapped[float | None] = mapped_column(Float)
    engine_type: Mapped[str | None] = mapped_column(String(100))
    fuel_type: Mapped[str | None] = mapped_column(String(50))
    gvwr: Mapped[str | None] = mapped_column(String(50))
    plant_city: Mapped[str | None] = mapped_column(String(100))
    plant_state: Mapped[str | None] = mapped_column(String(50))
    plant_country: Mapped[str | None] = mapped_column(String(50))
    manufacturer: Mapped[str | None] = mapped_column(String(100))

    # Pricing
    msrp: Mapped[float | None] = mapped_column(Float)
    invoice_price: Mapped[float | None] = mapped_column(Float)
    holdback: Mapped[float | None] = mapped_column(Float)
    true_dealer_cost: Mapped[float | None] = mapped_column(Float)

    # Scoring
    deal_score: Mapped[int | None] = mapped_column(Integer)
    aggressive_offer: Mapped[float | None] = mapped_column(Float)
    reasonable_offer: Mapped[float | None] = mapped_column(Float)
    likely_offer: Mapped[float | None] = mapped_column(Float)

    # Metadata
    decoded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ListingSighting(Base):
    """A specific listing of a vehicle on a platform."""
    __tablename__ = "listing_sightings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vin: Mapped[str] = mapped_column(String(17), index=True)
    platform: Mapped[str] = mapped_column(String(50))  # cargurus, autotrader, etc.
    listing_url: Mapped[str | None] = mapped_column(Text)
    asking_price: Mapped[float | None] = mapped_column(Float)
    msrp: Mapped[float | None] = mapped_column(Float)
    days_on_lot: Mapped[int | None] = mapped_column(Integer)
    days_on_platform: Mapped[int | None] = mapped_column(Integer)
    dealer_name: Mapped[str | None] = mapped_column(String(200))
    dealer_location: Mapped[str | None] = mapped_column(String(200))
    platform_deal_rating: Mapped[str | None] = mapped_column(String(50))
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_listing_vin_platform", "vin", "platform"),
    )


class InvoicePriceCache(Base):
    """Cached invoice pricing by year/make/model/trim."""
    __tablename__ = "invoice_price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer)
    make: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    trim: Mapped[str | None] = mapped_column(String(100))
    msrp: Mapped[float] = mapped_column(Float)
    invoice_price: Mapped[float] = mapped_column(Float)
    destination_charge: Mapped[float | None] = mapped_column(Float)
    holdback_amount: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_invoice_ymmt", "year", "make", "model", "trim"),
    )


class SavedVehicle(Base):
    """User's saved vehicle listing snapshot."""
    __tablename__ = "saved_vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    vin: Mapped[str | None] = mapped_column(String(17))
    platform: Mapped[str | None] = mapped_column(String(50))
    listing_url: Mapped[str | None] = mapped_column(Text)
    asking_price: Mapped[float | None] = mapped_column(Float)
    msrp: Mapped[float | None] = mapped_column(Float)
    year: Mapped[int | None] = mapped_column(Integer)
    make: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    trim: Mapped[str | None] = mapped_column(String(100))
    days_on_lot: Mapped[int | None] = mapped_column(Integer)
    dealer_name: Mapped[str | None] = mapped_column(String(200))
    dealer_location: Mapped[str | None] = mapped_column(String(200))
    deal_score: Mapped[int | None] = mapped_column(Integer)
    deal_grade: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_saved_user_vin", "user_id", "vin"),
    )


class DealAlert(Base):
    """User's deal alert criteria."""
    __tablename__ = "deal_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    make: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    year_min: Mapped[int | None] = mapped_column(Integer)
    year_max: Mapped[int | None] = mapped_column(Integer)
    price_max: Mapped[float | None] = mapped_column(Float)
    score_min: Mapped[int | None] = mapped_column(Integer)
    days_on_lot_min: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IncentiveProgram(Base):
    """Manufacturer rebates and incentives by make/model/region."""
    __tablename__ = "incentive_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    make: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)
    incentive_type: Mapped[str] = mapped_column(String(50))  # cash_back, apr, dealer_cash, lease
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float | None] = mapped_column(Float)
    apr_rate: Mapped[float | None] = mapped_column(Float)
    apr_months: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(String(50))  # SE, national, etc.
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    stackable: Mapped[bool | None] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ProcessedWebhookEvent(Base):
    """Tracks Stripe webhook event IDs to prevent duplicate processing."""
    __tablename__ = "processed_webhook_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MarketDataCache(Base):
    """Cached MarketCheck API responses with TTL."""
    __tablename__ = "market_data_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    make: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    data_type: Mapped[str] = mapped_column(String(50))  # "trends" or "stats"
    response_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_market_cache_make_model_type", "make", "model", "data_type"),
    )


class Dealership(Base):
    """Dealership API tier account."""
    __tablename__ = "dealerships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tier: Mapped[str] = mapped_column(String(50), default="standard")
    daily_rate_limit: Mapped[int] = mapped_column(Integer, default=1000)
    monthly_rate_limit: Mapped[int] = mapped_column(Integer, default=25000)
    requests_today: Mapped[int] = mapped_column(Integer, default=0)
    requests_this_month: Mapped[int] = mapped_column(Integer, default=0)
    last_request_date: Mapped[date | None] = mapped_column(Date)
    last_request_month: Mapped[str | None] = mapped_column(String(7))  # e.g. "2026-02"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
