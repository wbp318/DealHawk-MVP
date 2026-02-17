"""Add dealerships and market_data_cache tables for Phase 4.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_data_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cache_key", sa.String(255), nullable=False, unique=True),
        sa.Column("make", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("data_type", sa.String(50), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()),
    )
    with op.batch_alter_table("market_data_cache") as batch_op:
        batch_op.create_index(
            "ix_market_cache_make_model_type", ["make", "model", "data_type"]
        )

    op.create_table(
        "dealerships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("api_key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("tier", sa.String(50), default="standard"),
        sa.Column("daily_rate_limit", sa.Integer(), default=1000),
        sa.Column("monthly_rate_limit", sa.Integer(), default=25000),
        sa.Column("requests_today", sa.Integer(), default=0),
        sa.Column("requests_this_month", sa.Integer(), default=0),
        sa.Column("last_request_date", sa.Date(), nullable=True),
        sa.Column("last_request_month", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("dealerships")
    op.drop_table("market_data_cache")
