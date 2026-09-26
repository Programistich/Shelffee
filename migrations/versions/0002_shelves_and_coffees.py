"""shelves, shelf members and coffees

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shelves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "shelf_members",
        sa.Column(
            "shelf_id",
            sa.Integer(),
            sa.ForeignKey("shelves.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "coffees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "shelf_id",
            sa.Integer(),
            sa.ForeignKey("shelves.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_coffees_shelf_id", "coffees", ["shelf_id"])


def downgrade() -> None:
    op.drop_index("ix_coffees_shelf_id", table_name="coffees")
    op.drop_table("coffees")
    op.drop_table("shelf_members")
    op.drop_table("shelves")
