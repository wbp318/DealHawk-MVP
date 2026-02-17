"""Add hashed_password to dealerships for dashboard login.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("dealerships") as batch_op:
        batch_op.add_column(sa.Column("hashed_password", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("dealerships") as batch_op:
        batch_op.drop_column("hashed_password")
