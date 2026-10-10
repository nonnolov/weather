"""Add nullable source link and frozen rain delivery evidence.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch operations support SQLite tests and regular PostgreSQL ALTER TABLE.
    # No defaults or backfill: historical provenance is unknown.
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.add_column(sa.Column("forecast_run_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rain_evidence", sa.JSON(none_as_null=True), nullable=True))
        batch.create_foreign_key(
            "fk_notification_forecast_run", "forecast_runs", ["forecast_run_id"], ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Destructive rollback: evidence cannot be recovered without a backup.
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_constraint("fk_notification_forecast_run", type_="foreignkey")
        batch.drop_column("rain_evidence")
        batch.drop_column("forecast_run_id")
