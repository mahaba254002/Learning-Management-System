"""add password_changed_at to users

Revision ID: e1a2b3c4d5f6
Revises: ca5b2e8f6fde
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a2b3c4d5f6'
down_revision: Union[str, None] = 'ca5b2e8f6fde'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill existing rows to created_at so nobody's current, valid
    # session is retroactively invalidated by this migration.
    op.execute("UPDATE users SET password_changed_at = created_at WHERE password_changed_at IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')