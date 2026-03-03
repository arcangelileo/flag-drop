import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FlagValue(Base):
    __tablename__ = "flag_values"
    __table_args__ = (
        UniqueConstraint("flag_id", "environment_id", name="uq_flag_environment"),
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
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="false")  # JSON-encoded
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    flag: Mapped["Flag"] = relationship(back_populates="flag_values")  # noqa: F821
    environment: Mapped["Environment"] = relationship(  # noqa: F821
        back_populates="flag_values"
    )

    def __repr__(self) -> str:
        return f"<FlagValue flag={self.flag_id} env={self.environment_id} enabled={self.enabled}>"
