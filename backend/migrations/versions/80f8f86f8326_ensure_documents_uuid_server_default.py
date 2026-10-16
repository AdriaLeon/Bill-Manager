"""ensure documents uuid server default

Revision ID: 80f8f86f8326
Revises: 10024301c57c
Create Date: 2026-10-16 12:06:41.317216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80f8f86f8326'
down_revision: Union[str, Sequence[str], None] = '10024301c57c'
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