"""Initial schema — locations, forecast_runs, hourly_forecasts, daily_forecasts, observations

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── locations ─────────────────────────────────────────────────────────────
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("provider", sa.String(64), nullable=False, server_default="open_meteo"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_locations_id", "locations", ["id"])
    op.create_index("ix_locations_slug", "locations", ["slug"], unique=True)

    # ── forecast_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_run_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forecast_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("raw_provider_metadata", sa.String(2048), nullable=True),
    )
    op.create_index("ix_forecast_runs_id", "forecast_runs", ["id"])
    op.create_index("ix_forecast_runs_location_id", "forecast_runs", ["location_id"])

    # ── hourly_forecasts ──────────────────────────────────────────────────────
    op.create_table(
        "hourly_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("forecast_run_id", sa.Integer(), sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valid_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_2m", sa.Float(), nullable=True),
        sa.Column("apparent_temperature", sa.Float(), nullable=True),
        sa.Column("dewpoint_2m", sa.Float(), nullable=True),
        sa.Column("relative_humidity_2m", sa.Float(), nullable=True),
        sa.Column("precipitation", sa.Float(), nullable=True),
        sa.Column("precipitation_probability", sa.Float(), nullable=True),
        sa.Column("rain", sa.Float(), nullable=True),
        sa.Column("snowfall", sa.Float(), nullable=True),
        sa.Column("snow_depth", sa.Float(), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("surface_pressure", sa.Float(), nullable=True),
        sa.Column("wind_speed_10m", sa.Float(), nullable=True),
        sa.Column("wind_direction_10m", sa.Float(), nullable=True),
        sa.Column("wind_gusts_10m", sa.Float(), nullable=True),
        sa.Column("visibility", sa.Float(), nullable=True),
        sa.Column("uv_index", sa.Float(), nullable=True),
        sa.Column("is_day", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("forecast_run_id", "valid_time", name="uq_hourly_run_time"),
    )
    op.create_index("ix_hourly_forecasts_id", "hourly_forecasts", ["id"])
    op.create_index("ix_hourly_forecasts_forecast_run_id", "hourly_forecasts", ["forecast_run_id"])
    op.create_index("ix_hourly_location_time", "hourly_forecasts", ["forecast_run_id", "valid_time"])

    # ── daily_forecasts ───────────────────────────────────────────────────────
    op.create_table(
        "daily_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("forecast_run_id", sa.Integer(), sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("temperature_2m_max", sa.Float(), nullable=True),
        sa.Column("temperature_2m_min", sa.Float(), nullable=True),
        sa.Column("apparent_temperature_max", sa.Float(), nullable=True),
        sa.Column("apparent_temperature_min", sa.Float(), nullable=True),
        sa.Column("precipitation_sum", sa.Float(), nullable=True),
        sa.Column("precipitation_probability_max", sa.Float(), nullable=True),
        sa.Column("rain_sum", sa.Float(), nullable=True),
        sa.Column("snowfall_sum", sa.Float(), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("wind_speed_10m_max", sa.Float(), nullable=True),
        sa.Column("wind_gusts_10m_max", sa.Float(), nullable=True),
        sa.Column("wind_direction_10m_dominant", sa.Float(), nullable=True),
        sa.Column("uv_index_max", sa.Float(), nullable=True),
        sa.Column("sunrise", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sunset", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("forecast_run_id", "forecast_date", name="uq_daily_run_date"),
    )
    op.create_index("ix_daily_forecasts_id", "daily_forecasts", ["id"])
    op.create_index("ix_daily_forecasts_forecast_run_id", "daily_forecasts", ["forecast_run_id"])
    op.create_index("ix_daily_location_date", "daily_forecasts", ["forecast_run_id", "forecast_date"])

    # ── observations ──────────────────────────────────────────────────────────
    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("temperature_2m", sa.Float(), nullable=True),
        sa.Column("apparent_temperature", sa.Float(), nullable=True),
        sa.Column("dewpoint_2m", sa.Float(), nullable=True),
        sa.Column("relative_humidity_2m", sa.Float(), nullable=True),
        sa.Column("precipitation", sa.Float(), nullable=True),
        sa.Column("rain", sa.Float(), nullable=True),
        sa.Column("snowfall", sa.Float(), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("surface_pressure", sa.Float(), nullable=True),
        sa.Column("wind_speed_10m", sa.Float(), nullable=True),
        sa.Column("wind_direction_10m", sa.Float(), nullable=True),
        sa.Column("wind_gusts_10m", sa.Float(), nullable=True),
        sa.Column("visibility", sa.Float(), nullable=True),
        sa.Column("uv_index", sa.Float(), nullable=True),
        sa.Column("is_day", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_observations_id", "observations", ["id"])
    op.create_index("ix_observations_location_id", "observations", ["location_id"])
    op.create_index("ix_obs_location_time", "observations", ["location_id", "observed_at"])


def downgrade() -> None:
    op.drop_table("observations")
    op.drop_table("daily_forecasts")
    op.drop_table("hourly_forecasts")
    op.drop_table("forecast_runs")
    op.drop_table("locations")
