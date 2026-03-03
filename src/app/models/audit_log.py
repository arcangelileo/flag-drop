import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # created, updated, deleted, toggled
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # flag, flag_value, environment, project
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    flag_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("flags.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="audit_logs")  # noqa: F821
    flag: Mapped["Flag | None"] = relationship(back_populates="audit_logs")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type} {self.entity_id}>"
