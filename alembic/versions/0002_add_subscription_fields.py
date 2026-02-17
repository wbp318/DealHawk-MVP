"""Add subscription fields to users table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(255), unique=True))
        batch_op.add_column(sa.Column("subscription_tier", sa.String(20), server_default="free"))
        batch_op.add_column(sa.Column("subscription_status", sa.String(20), server_default="active"))
        batch_op.add_column(sa.Column("subscription_stripe_id", sa.String(255)))
        batch_op.add_column(sa.Column("subscription_current_period_end", sa.DateTime()))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("subscription_current_period_end")
        batch_op.drop_column("subscription_stripe_id")
        batch_op.drop_column("subscription_status")
        batch_op.drop_column("subscription_tier")
        batch_op.drop_column("stripe_customer_id")
