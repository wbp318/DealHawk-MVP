"""Baseline: existing 7-table schema from Phase 2.

Revision ID: 0001
Revises: None
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100)),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "vehicles",
        sa.Column("vin", sa.String(17), primary_key=True),
        sa.Column("year", sa.Integer()),
        sa.Column("make", sa.String(50)),
        sa.Column("model", sa.String(100)),
        sa.Column("trim", sa.String(100)),
        sa.Column("body_class", sa.String(100)),
        sa.Column("drive_type", sa.String(50)),
        sa.Column("engine_cylinders", sa.Integer()),
        sa.Column("engine_displacement", sa.Float()),
        sa.Column("engine_type", sa.String(100)),
        sa.Column("fuel_type", sa.String(50)),
        sa.Column("gvwr", sa.String(50)),
        sa.Column("plant_city", sa.String(100)),
        sa.Column("plant_state", sa.String(50)),
        sa.Column("plant_country", sa.String(50)),
        sa.Column("manufacturer", sa.String(100)),
        sa.Column("msrp", sa.Float()),
        sa.Column("invoice_price", sa.Float()),
        sa.Column("holdback", sa.Float()),
        sa.Column("true_dealer_cost", sa.Float()),
        sa.Column("deal_score", sa.Integer()),
        sa.Column("aggressive_offer", sa.Float()),
        sa.Column("reasonable_offer", sa.Float()),
        sa.Column("likely_offer", sa.Float()),
        sa.Column("decoded_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "listing_sightings",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("vin", sa.String(17), index=True),
        sa.Column("platform", sa.String(50)),
        sa.Column("listing_url", sa.Text()),
        sa.Column("asking_price", sa.Float()),
        sa.Column("msrp", sa.Float()),
        sa.Column("days_on_lot", sa.Integer()),
        sa.Column("days_on_platform", sa.Integer()),
        sa.Column("dealer_name", sa.String(200)),
        sa.Column("dealer_location", sa.String(200)),
        sa.Column("platform_deal_rating", sa.String(50)),
        sa.Column("first_seen", sa.DateTime()),
        sa.Column("last_seen", sa.DateTime()),
    )
    op.create_index("ix_listing_vin_platform", "listing_sightings", ["vin", "platform"])

    op.create_table(
        "invoice_price_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("year", sa.Integer()),
        sa.Column("make", sa.String(50)),
        sa.Column("model", sa.String(100)),
        sa.Column("trim", sa.String(100)),
        sa.Column("msrp", sa.Float()),
        sa.Column("invoice_price", sa.Float()),
        sa.Column("destination_charge", sa.Float()),
        sa.Column("holdback_amount", sa.Float()),
        sa.Column("source", sa.String(100)),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_invoice_ymmt", "invoice_price_cache", ["year", "make", "model", "trim"])

    op.create_table(
        "incentive_programs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("make", sa.String(50), index=True),
        sa.Column("model", sa.String(100)),
        sa.Column("year", sa.Integer()),
        sa.Column("incentive_type", sa.String(50)),
        sa.Column("name", sa.String(200)),
        sa.Column("amount", sa.Float()),
        sa.Column("apr_rate", sa.Float()),
        sa.Column("apr_months", sa.Integer()),
        sa.Column("region", sa.String(50)),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("stackable", sa.Boolean(), default=True),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_at", sa.DateTime()),
    )

    op.create_table(
        "saved_vehicles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("vin", sa.String(17)),
        sa.Column("platform", sa.String(50)),
        sa.Column("listing_url", sa.Text()),
        sa.Column("asking_price", sa.Float()),
        sa.Column("msrp", sa.Float()),
        sa.Column("year", sa.Integer()),
        sa.Column("make", sa.String(50)),
        sa.Column("model", sa.String(100)),
        sa.Column("trim", sa.String(100)),
        sa.Column("days_on_lot", sa.Integer()),
        sa.Column("dealer_name", sa.String(200)),
        sa.Column("dealer_location", sa.String(200)),
        sa.Column("deal_score", sa.Integer()),
        sa.Column("deal_grade", sa.String(10)),
        sa.Column("notes", sa.Text()),
        sa.Column("saved_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_saved_user_vin", "saved_vehicles", ["user_id", "vin"])

    op.create_table(
        "deal_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("make", sa.String(50)),
        sa.Column("model", sa.String(100)),
        sa.Column("year_min", sa.Integer()),
        sa.Column("year_max", sa.Integer()),
        sa.Column("price_max", sa.Float()),
        sa.Column("score_min", sa.Integer()),
        sa.Column("days_on_lot_min", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("deal_alerts")
    op.drop_table("saved_vehicles")
    op.drop_table("incentive_programs")
    op.drop_index("ix_invoice_ymmt", table_name="invoice_price_cache")
    op.drop_table("invoice_price_cache")
    op.drop_index("ix_listing_vin_platform", table_name="listing_sightings")
    op.drop_table("listing_sightings")
    op.drop_table("vehicles")
    op.drop_table("users")
