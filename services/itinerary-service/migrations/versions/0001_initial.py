"""Create itinerary aggregate and transactional outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "itineraries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("departure_airport_id", sa.Integer(), nullable=False),
        sa.Column("arrival_airport_id", sa.Integer(), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("departure_airport_id <> arrival_airport_id"),
        sa.CheckConstraint("duration_days BETWEEN 1 AND 365"),
    )
    op.create_index("ix_itinerary_user_created", "itineraries", ["user_id", "created_at", "id"])
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("trace_context", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_outbox_published_at", "outbox", ["published_at"])


def downgrade():
    op.drop_table("outbox")
    op.drop_table("itineraries")
