"""Add LINE notification delivery log for alert deduplication.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("recipient_id", sa.String(128), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "channel", "recipient_id", "dedupe_key", name="uq_notification_dedupe"
        ),
    )
    op.create_index("ix_notification_deliveries_id", "notification_deliveries", ["id"])
    op.create_index(
        "ix_notification_deliveries_location_id", "notification_deliveries", ["location_id"]
    )
    op.create_index(
        "ix_notification_location_created",
        "notification_deliveries",
        ["location_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
