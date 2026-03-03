from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_record import UsageRecord


async def record_evaluation(
    db: AsyncSession,
    flag_id: str,
    environment_id: str,
) -> None:
    """Increment the evaluation count for a flag+environment+today."""
    today = date.today()
    result = await db.execute(
        select(UsageRecord).where(
            UsageRecord.flag_id == flag_id,
            UsageRecord.environment_id == environment_id,
            UsageRecord.record_date == today,
        )
    )
    record = result.scalar_one_or_none()

    if record:
        record.evaluation_count += 1
    else:
        record = UsageRecord(
            flag_id=flag_id,
            environment_id=environment_id,
            record_date=today,
            evaluation_count=1,
        )
        db.add(record)
    await db.flush()


async def get_usage_for_project(
    db: AsyncSession,
    project_id: str,
    days: int = 30,
) -> list[UsageRecord]:
    """Get usage records for all flags in a project for the last N days."""
    from sqlalchemy.orm import selectinload
    from app.models.flag import Flag

    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(UsageRecord)
        .join(Flag, UsageRecord.flag_id == Flag.id)
        .where(
            Flag.project_id == project_id,
            UsageRecord.record_date >= cutoff,
        )
        .options(selectinload(UsageRecord.flag))
        .order_by(UsageRecord.record_date.desc())
    )
    return list(result.scalars().all())


async def get_total_evaluations_for_project(
    db: AsyncSession,
    project_id: str,
    days: int = 30,
) -> int:
    from sqlalchemy import func
    from app.models.flag import Flag

    cutoff = date.today() - timedelta(days=days)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageRecord.evaluation_count), 0))
        .join(Flag, UsageRecord.flag_id == Flag.id)
        .where(
            Flag.project_id == project_id,
            UsageRecord.record_date >= cutoff,
        )
    )
    return result.scalar() or 0
