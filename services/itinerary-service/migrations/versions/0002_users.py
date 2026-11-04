"""Add user profiles for gateway registration."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("username", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
    )


def downgrade():
    op.drop_table("users")
