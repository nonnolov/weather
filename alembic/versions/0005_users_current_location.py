"""Add external users with optional current location.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("current_location_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["current_location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("external_id"),
    )
    op.create_index("ix_users_current_location_id", "users", ["current_location_id"])


def downgrade() -> None:
    op.drop_index("ix_users_current_location_id", table_name="users")
    op.drop_table("users")
