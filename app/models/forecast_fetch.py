"""Shared acquisition cache and conservative, durable request reservations."""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ForecastFetchCache(Base):
    __tablename__ = "forecast_fetch_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict | None] = mapped_column(JSON)


class ProviderRequestBudget(Base):
    __tablename__ = "provider_request_budgets"
    __table_args__ = (CheckConstraint("reserved >= 0", name="ck_provider_reserved_positive"),)
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    period: Mapped[str] = mapped_column(String(12), primary_key=True)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
