"""Capture request metadata on new audit events; historical values stay unknown."""
from alembic import op
import sqlalchemy as sa

revision = "d6f7a8b9c0e1"
down_revision = "c5e6f7a8b9d0"
branch_labels = None
depends_on = None


def upgrade():
    for name, length in [("ip_address", 45), ("request_method", 10), ("request_path", 500)]:
        op.add_column("audit_events", sa.Column(name, sa.String(length), nullable=True))
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade():
    op.drop_index("ix_audit_events_action", "audit_events")
    for name in ["request_path", "request_method", "ip_address"]:
        op.drop_column("audit_events", name)
