"""Store provider current-condition snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "current_conditions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("forecast_run_id", sa.Integer(), nullable=False),
        sa.Column("valid_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("temperature_2m", sa.Float(), nullable=True),
        sa.Column("apparent_temperature", sa.Float(), nullable=True),
        sa.Column("relative_humidity_2m", sa.Float(), nullable=True),
        sa.Column("precipitation", sa.Float(), nullable=True),
        sa.Column("rain", sa.Float(), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("surface_pressure", sa.Float(), nullable=True),
        sa.Column("wind_speed_10m", sa.Float(), nullable=True),
        sa.Column("wind_direction_10m", sa.Float(), nullable=True),
        sa.Column("wind_gusts_10m", sa.Float(), nullable=True),
        sa.Column("is_day", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["forecast_run_id"], ["forecast_runs.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("forecast_run_id", name="uq_current_conditions_run"),
    )
    op.create_index("ix_current_conditions_id", "current_conditions", ["id"])
    op.create_index(
        "ix_current_conditions_forecast_run_id",
        "current_conditions",
        ["forecast_run_id"],
    )


def downgrade():
    op.drop_index(
        "ix_current_conditions_forecast_run_id", table_name="current_conditions"
    )
    op.drop_index("ix_current_conditions_id", table_name="current_conditions")
    op.drop_table("current_conditions")
