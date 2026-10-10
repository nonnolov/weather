"""Durable fail-closed intraday send intents.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "intraday_send_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_id", sa.String(128), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("delivery_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("recipient_id", "location_id", "event_id", name="uq_intraday_attempt_event"),
        sa.CheckConstraint("status IN ('pending', 'accepted')", name="ck_intraday_attempt_status"),
    )
    op.create_index("uq_intraday_pending_scope", "intraday_send_attempts",
                    ["recipient_id", "location_id"], unique=True,
                    postgresql_where=sa.text("status = 'pending'"),
                    sqlite_where=sa.text("status = 'pending'"))


def downgrade():
    # Destructive: removes unresolved-send protection. Do not use for rollback.
    op.drop_table("intraday_send_attempts")
