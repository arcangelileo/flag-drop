import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Flag(Base):
    __tablename__ = "flags"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_flag_project_key"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    flag_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="boolean"
    )  # boolean, string, number, json
    default_value: Mapped[str] = mapped_column(
        Text, nullable=False, default="false"
    )  # JSON-encoded
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="flags")  # noqa: F821
    flag_values: Mapped[list["FlagValue"]] = relationship(  # noqa: F821
        back_populates="flag", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        back_populates="flag", cascade="all, delete-orphan"
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(  # noqa: F821
        back_populates="flag", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Flag {self.key} ({self.flag_type})>"
