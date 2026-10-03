from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """External user identity and its current resolved location."""

    __tablename__ = "users"

    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_location: Mapped["Location | None"] = relationship(  # noqa: F821
        "Location", back_populates="current_users"
    )

    def __repr__(self) -> str:
        return f"<User external_id={self.external_id!r}>"
