import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    entity_type: str,
    entity_id: str,
    project_id: str,
    user_id: str | None = None,
    flag_id: str | None = None,
    old_value: dict | str | None = None,
    new_value: dict | str | None = None,
) -> AuditLog:
    """Record an action in the audit log."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        project_id=project_id,
        user_id=user_id,
        flag_id=flag_id,
        old_value=json.dumps(old_value) if old_value is not None else None,
        new_value=json.dumps(new_value) if new_value is not None else None,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_audit_logs_for_project(
    db: AsyncSession,
    project_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .options(selectinload(AuditLog.user), selectinload(AuditLog.flag))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_audit_logs_for_project(
    db: AsyncSession,
    project_id: str,
) -> int:
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.project_id == project_id)
    )
    return result.scalar() or 0
