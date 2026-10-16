"""add server uuid default

Revision ID: 10024301c57c
Revises: a471443d7727
Create Date: 2026-10-16 11:57:23.080340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10024301c57c'
down_revision: Union[str, Sequence[str], None] = 'a471443d7727'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.alter_column(
        "documents",
        "id",
        existing_type=sa.UUID(),
        existing_nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "id",
        existing_type=sa.UUID(),
        existing_nullable=False,
        server_default=None,
    )