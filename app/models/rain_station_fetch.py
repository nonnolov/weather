"""Append-only station fetches; kept separate from location observations."""
from datetime import datetime,timezone
from sqlalchemy import CheckConstraint,DateTime,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database import Base

class RainStationFetch(Base):
    __tablename__ = "rain_station_fetches"
    __table_args__ = (
        UniqueConstraint("station_id","poll_slot",name="uq_rain_station_poll_slot"),
        CheckConstraint("status IN ('quarantined','failed')",name="ck_rain_station_fetch_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(Integer,nullable=False,index=True)
    poll_slot: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,index=True)
    status: Mapped[str] = mapped_column(String(24),nullable=False)
    error_code: Mapped[str|None] = mapped_column(String(40),nullable=True)
    raw_sha256: Mapped[str|None] = mapped_column(String(64),nullable=True)
    raw_body: Mapped[str|None] = mapped_column(Text,nullable=True)
    evidence: Mapped[dict|None] = mapped_column(JSON,nullable=True)
