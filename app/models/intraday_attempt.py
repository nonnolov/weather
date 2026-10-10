"""Durable intraday send intent; never counts as accepted delivery evidence."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IntradaySendAttempt(Base):
    __tablename__ = "intraday_send_attempts"
    __table_args__ = (
        UniqueConstraint("recipient_id", "location_id", "event_id", name="uq_intraday_attempt_event"),
        CheckConstraint("status IN ('pending', 'accepted')", name="ck_intraday_attempt_status"),
        Index("uq_intraday_pending_scope", "recipient_id", "location_id", unique=True,
              postgresql_where=text("status = 'pending'"), sqlite_where=text("status = 'pending'")),
    )
    # No foreign keys: intent must survive source/user deletion, and independent
    # intent commits must not wait on the delivery transaction's location locks.
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[str] = mapped_column(String(128), nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    delivery_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                              default=lambda: datetime.now(timezone.utc))
