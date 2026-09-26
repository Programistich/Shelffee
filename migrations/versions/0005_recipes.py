"""recipes

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-05 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("coffees", "grind")
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "coffee_id",
            sa.Integer(),
            sa.ForeignKey("coffees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("dose_grams", sa.Float(), nullable=False),
        sa.Column("grind", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("recipes")
    op.add_column(
        "coffees", sa.Column("grind", sa.String(32), nullable=False, server_default="")
    )
