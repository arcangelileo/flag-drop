import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6B7280")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="environments")  # noqa: F821
    flag_values: Mapped[list["FlagValue"]] = relationship(  # noqa: F821
        back_populates="environment", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["APIKey"]] = relationship(  # noqa: F821
        back_populates="environment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Environment {self.name} ({self.project_id})>"
