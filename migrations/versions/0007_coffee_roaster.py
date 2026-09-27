"""coffee roaster

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-07 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("coffees", sa.Column("roaster", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("coffees", "roaster")
