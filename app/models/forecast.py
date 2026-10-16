from datetime import datetime, date, timezone
from sqlalchemy import (
    String, Float, Integer, Boolean, DateTime, Date,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ForecastRun(Base):
    """
    One retrieval of a forecast from a provider.
    Every retrieval is stored as an immutable snapshot — never overwritten.
    """

    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # The nominal initialisation time of the underlying NWP model run (if known)
    model_run_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forecast_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    raw_provider_metadata: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="forecast_runs")  # noqa: F821
    hourly_forecasts: Mapped[list["HourlyForecast"]] = relationship(
        "HourlyForecast", back_populates="forecast_run", cascade="all, delete-orphan"
    )
    daily_forecasts: Mapped[list["DailyForecast"]] = relationship(
        "DailyForecast", back_populates="forecast_run", cascade="all, delete-orphan"
    )
    current_conditions: Mapped["CurrentConditions | None"] = relationship(
        "CurrentConditions", back_populates="forecast_run", cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<ForecastRun id={self.id} location_id={self.location_id} provider={self.provider!r}>"


class CurrentConditions(Base):
    """Provider current-conditions snapshot captured with a ForecastRun."""

    __tablename__ = "current_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    forecast_run_id: Mapped[int] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    valid_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    apparent_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_humidity_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    surface_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_gusts_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_day: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    forecast_run: Mapped["ForecastRun"] = relationship(
        "ForecastRun", back_populates="current_conditions"
    )


class HourlyForecast(Base):
    """One hour of forecast data within a ForecastRun."""

    __tablename__ = "hourly_forecasts"
    __table_args__ = (
        UniqueConstraint("forecast_run_id", "valid_time", name="uq_hourly_run_time"),
        Index("ix_hourly_location_time", "forecast_run_id", "valid_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    forecast_run_id: Mapped[int] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valid_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Core meteorological variables
    temperature_2m: Mapped[float | None] = mapped_column(Float, nullable=True)          # °C
    apparent_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)    # °C
    dewpoint_2m: Mapped[float | None] = mapped_column(Float, nullable=True)             # °C
    relative_humidity_2m: Mapped[float | None] = mapped_column(Float, nullable=True)   # %
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)           # mm
    precipitation_probability: Mapped[float | None] = mapped_column(Float, nullable=True)  # %
    rain: Mapped[float | None] = mapped_column(Float, nullable=True)                    # mm
    snowfall: Mapped[float | None] = mapped_column(Float, nullable=True)                # cm
    snow_depth: Mapped[float | None] = mapped_column(Float, nullable=True)              # m
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)            # WMO code
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)             # %
    surface_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)        # hPa
    wind_speed_10m: Mapped[float | None] = mapped_column(Float, nullable=True)          # km/h
    wind_direction_10m: Mapped[float | None] = mapped_column(Float, nullable=True)      # °
    wind_gusts_10m: Mapped[float | None] = mapped_column(Float, nullable=True)          # km/h
    visibility: Mapped[float | None] = mapped_column(Float, nullable=True)              # m
    uv_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_day: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Relationship
    forecast_run: Mapped["ForecastRun"] = relationship("ForecastRun", back_populates="hourly_forecasts")

    def __repr__(self) -> str:
        return f"<HourlyForecast run={self.forecast_run_id} time={self.valid_time}>"


class DailyForecast(Base):
    """One day of forecast data within a ForecastRun."""

    __tablename__ = "daily_forecasts"
    __table_args__ = (
        UniqueConstraint("forecast_run_id", "forecast_date", name="uq_daily_run_date"),
        Index("ix_daily_location_date", "forecast_run_id", "forecast_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    forecast_run_id: Mapped[int] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Daily aggregates
    temperature_2m_max: Mapped[float | None] = mapped_column(Float, nullable=True)      # °C
    temperature_2m_min: Mapped[float | None] = mapped_column(Float, nullable=True)      # °C
    apparent_temperature_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    apparent_temperature_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_sum: Mapped[float | None] = mapped_column(Float, nullable=True)       # mm
    precipitation_probability_max: Mapped[float | None] = mapped_column(Float, nullable=True)  # %
    rain_sum: Mapped[float | None] = mapped_column(Float, nullable=True)                # mm
    snowfall_sum: Mapped[float | None] = mapped_column(Float, nullable=True)            # cm
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wind_speed_10m_max: Mapped[float | None] = mapped_column(Float, nullable=True)      # km/h
    wind_gusts_10m_max: Mapped[float | None] = mapped_column(Float, nullable=True)      # km/h
    wind_direction_10m_dominant: Mapped[float | None] = mapped_column(Float, nullable=True)  # °
    uv_index_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    sunrise: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sunset: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship
    forecast_run: Mapped["ForecastRun"] = relationship("ForecastRun", back_populates="daily_forecasts")

    def __repr__(self) -> str:
        return f"<DailyForecast run={self.forecast_run_id} date={self.forecast_date}>"
