"""coffee attributes

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-04 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("coffees", sa.Column("country", sa.String(64), nullable=False))
    op.add_column(
        "coffees", sa.Column("flavor_notes", sa.ARRAY(sa.String(64)), nullable=False)
    )
    op.add_column("coffees", sa.Column("roast", sa.String(16), nullable=False))
    op.add_column("coffees", sa.Column("weight_grams", sa.Integer(), nullable=False))
    op.add_column("coffees", sa.Column("grind", sa.String(32), nullable=False))
    op.add_column("coffees", sa.Column("process", sa.String(64), nullable=False))
    op.add_column("coffees", sa.Column("region", sa.String(128), nullable=True))
    op.add_column("coffees", sa.Column("variety", sa.String(128), nullable=True))
    op.add_column("coffees", sa.Column("altitude_masl", sa.Integer(), nullable=True))
    op.add_column("coffees", sa.Column("farm", sa.String(128), nullable=True))
    op.add_column("coffees", sa.Column("sensory_scale", sa.Integer(), nullable=True))
    op.add_column("coffees", sa.Column("acidity", sa.Integer(), nullable=True))
    op.add_column("coffees", sa.Column("sweetness", sa.Integer(), nullable=True))
    op.add_column("coffees", sa.Column("bitterness", sa.Integer(), nullable=True))
    op.add_column("coffees", sa.Column("body", sa.Integer(), nullable=True))


def downgrade() -> None:
    for column in (
        "body",
        "bitterness",
        "sweetness",
        "acidity",
        "sensory_scale",
        "farm",
        "altitude_masl",
        "variety",
        "region",
        "process",
        "grind",
        "weight_grams",
        "roast",
        "flavor_notes",
        "country",
    ):
        op.drop_column("coffees", column)
