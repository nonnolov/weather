"""Shared forecast acquisition cache and persistent provider budgets."""
from alembic import op
import sqlalchemy as sa
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("forecast_fetch_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True)),
        sa.Column("retry_after", sa.DateTime(timezone=True)),
        sa.Column("payload", sa.JSON()))
    op.create_table("provider_request_budgets",
        sa.Column("provider", sa.String(32), primary_key=True),
        sa.Column("period", sa.String(12), primary_key=True),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.CheckConstraint("reserved >= 0", name="ck_provider_reserved_positive"))


def downgrade():
    op.drop_table("provider_request_budgets")
    op.drop_table("forecast_fetch_cache")
