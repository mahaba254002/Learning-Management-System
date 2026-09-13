"""add PASSWORD_RESET verification purpose

Revision ID: d75fe944c53f
Revises: 5934dac1f22c
Create Date: 2026-09-10
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd75fe944c53f'
down_revision: Union[str, None] = '5934dac1f22c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alembic's autogenerate cannot detect additions to an existing
    # Postgres ENUM type, so this is added by hand — same situation as the
    # ARCHIVED status migration earlier.
    op.execute("ALTER TYPE verification_purpose ADD VALUE IF NOT EXISTS 'PASSWORD_RESET'")


def downgrade() -> None:
    # Postgres does not support removing a value from an existing ENUM
    # type directly. A true downgrade would require recreating the type
    # without 'PASSWORD_RESET' and migrating dependent rows over —
    # deliberately not automated here, same reasoning as prior enum
    # migrations in this project.
    pass