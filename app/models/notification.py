from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NotificationDelivery(Base):
    """Persistent LINE delivery record used for alert deduplication."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("channel", "recipient_id", "dedupe_key", name="uq_notification_dedupe"),
        Index("ix_notification_location_created", "location_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Legacy and non-rain deliveries remain unknown. Run deletion must not
    # delete delivery history; the frozen evidence retains the original ID.
    forecast_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("forecast_runs.id", name="fk_notification_forecast_run", ondelete="SET NULL"),
        nullable=True,
    )
    rain_evidence: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    location: Mapped["Location"] = relationship("Location")  # noqa: F821
