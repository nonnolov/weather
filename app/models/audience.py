"""Deduplicated visitor/location counters without coordinates or raw identities."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class AudienceMember(Base):
    __tablename__ = "audience_members"
    __table_args__ = (CheckConstraint("kind IN ('browser', 'location')", name="ck_audience_kind"),)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    identity_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
