"""Unique visitors and successfully saved user GPS locations."""
from alembic import op
import sqlalchemy as sa
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("audience_members",
        sa.Column("kind", sa.String(8), primary_key=True),
        sa.Column("identity_hash", sa.String(64), primary_key=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('browser', 'location')", name="ck_audience_kind"))

def downgrade():
    op.drop_table("audience_members")
