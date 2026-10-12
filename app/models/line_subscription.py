from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class LineSubscription(Base):
    __tablename__ = "line_subscriptions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.external_id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    friend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    friend_event_time: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
