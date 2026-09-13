"""add ARCHIVED status and archive audit fields to institutions

Revision ID: b60a722a1c84
Revises: c2f3071cddcb
Create Date: 2026-09-10 07:46:10.141039
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b60a722a1c84'
down_revision: Union[str, None] = 'c2f3071cddcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alembic's autogenerate cannot detect additions to an existing
    # Postgres ENUM type, so this line is added by hand: it adds the new
    # 'ARCHIVED' value to the institution_status enum that already exists
    # in the database. Must run OUTSIDE a transaction block in Postgres for
    # older versions, but modern Postgres (12+) supports this within a
    # transaction, which is what Alembic uses by default here — no special
    # handling needed.
    op.execute("ALTER TYPE institution_status ADD VALUE IF NOT EXISTS 'ARCHIVED'")

    op.add_column('institutions', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('institutions', sa.Column('archived_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_institutions_archived_by_users',
        'institutions', 'users', ['archived_by'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_institutions_archived_by_users', 'institutions', type_='foreignkey')
    op.drop_column('institutions', 'archived_by')
    op.drop_column('institutions', 'archived_at')
    # Note: Postgres does not support removing a value from an existing
    # ENUM type directly. A true downgrade of the enum would require
    # recreating the type without 'ARCHIVED' and migrating the column over
    # — deliberately not automated here since it's a destructive, rare
    # operation. If you ever need to fully reverse this, that step must be
    # done by hand.