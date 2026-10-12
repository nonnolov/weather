"""Explicit LINE friend/location/notification consent."""
from alembic import op
import sqlalchemy as sa
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("line_subscriptions",
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.external_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("friend", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("consent_version", sa.String(32)),
        sa.Column("consented_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("friend_event_time", sa.BigInteger(), nullable=False, server_default="0"))

def downgrade():
    op.drop_table("line_subscriptions")
