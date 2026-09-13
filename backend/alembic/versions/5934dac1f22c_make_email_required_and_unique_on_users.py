"""make email required and unique on users

Revision ID: 5934dac1f22c
Revises: b60a722a1c84
Create Date: 2026-09-10 21:42:01.381604
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5934dac1f22c'
down_revision: Union[str, None] = 'b60a722a1c84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET email = 'unset-' || id || '@placeholder.local'
        WHERE email IS NULL
        """
    )

    op.alter_column('users', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)

    op.drop_index('ix_users_email', table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.alter_column('users', 'email',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)