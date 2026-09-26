"""shelf share token

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-03 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shelves", sa.Column("share_token", sa.String(32), nullable=True))
    op.execute("UPDATE shelves SET share_token = md5(random()::text) WHERE share_token IS NULL")
    op.alter_column("shelves", "share_token", nullable=False)
    op.create_unique_constraint("uq_shelves_share_token", "shelves", ["share_token"])


def downgrade() -> None:
    op.drop_constraint("uq_shelves_share_token", "shelves", type_="unique")
    op.drop_column("shelves", "share_token")
