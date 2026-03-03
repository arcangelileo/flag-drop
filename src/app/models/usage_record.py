import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("flag_id", "environment_id", "record_date", name="uq_flag_env_date"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    flag_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flags.id", ondelete="CASCADE"), nullable=False
    )
    environment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("environments.id", ondelete="CASCADE"), nullable=False
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    evaluation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    flag: Mapped["Flag"] = relationship(back_populates="usage_records")  # noqa: F821

    def __repr__(self) -> str:
        return f"<UsageRecord flag={self.flag_id} date={self.record_date} count={self.evaluation_count}>"
