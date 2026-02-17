from datetime import datetime, date
from sqlalchemy import String, Float, Integer, DateTime, Date, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
