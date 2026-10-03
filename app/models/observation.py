from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Observation(Base):
    """
    An actual observed (measured) weather value at a location.
    Used for forecast evaluation (MAE, RMSE, Bias).
    """

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("location_id", "observed_at", name="uq_observation_location_time"),
        Index("ix_obs_location_time", "location_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "open_meteo_historical"

    # Observed variables (mirrors HourlyForecast fields)
    temperature_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    apparent_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    dewpoint_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_humidity_2m: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain: Mapped[float | None] = mapped_column(Float, nullable=True)
    snowfall: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    surface_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_gusts_10m: Mapped[float | None] = mapped_column(Float, nullable=True)
    visibility: Mapped[float | None] = mapped_column(Float, nullable=True)
    uv_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_day: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    location: Mapped["Location"] = relationship("Location", back_populates="observations")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Observation id={self.id} location_id={self.location_id} at={self.observed_at}>"
