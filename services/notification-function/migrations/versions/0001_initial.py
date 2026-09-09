"""Independent notification history with idempotency key."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("itinerary_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("notifications")
