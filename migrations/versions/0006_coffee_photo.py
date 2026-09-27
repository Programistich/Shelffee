"""coffee photo

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-06 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("coffees", sa.Column("photo", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("coffees", "photo")
