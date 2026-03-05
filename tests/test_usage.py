"""Tests for the usage tracking service."""
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.services.auth import create_user
from app.services.projects import create_project
from app.services.flags import create_flag
from app.services.usage import (
    record_evaluation,
    get_usage_for_project,
    get_total_evaluations_for_project,
)
from app.models.usage_record import UsageRecord
from app.models.project import Project


async def _get_project_with_envs(db: AsyncSession, project_id: str) -> Project:
    """Helper to reload project with environments eagerly loaded."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.environments))
    )
    return result.scalar_one()


async def test_record_evaluation_creates_record(db: AsyncSession):
    """First evaluation should create a new usage record."""
    user = await create_user(db, "usage@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Usage Project", user.id)
    flag = await create_flag(db, project.id, "test_flag", flag_type="boolean")
    await db.commit()

    project = await _get_project_with_envs(db, project.id)
    env = project.environments[0]

    await record_evaluation(db, flag.id, env.id)
    await db.commit()

    result = await db.execute(
        select(UsageRecord).where(
            UsageRecord.flag_id == flag.id,
            UsageRecord.environment_id == env.id,
        )
    )
    record = result.scalar_one()
    assert record.evaluation_count == 1
    assert record.record_date == date.today()


async def test_record_evaluation_increments_count(db: AsyncSession):
    """Subsequent evaluations should increment the count, not create new records."""
    user = await create_user(db, "usage2@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Usage Project", user.id)
    flag = await create_flag(db, project.id, "test_flag", flag_type="boolean")
    await db.commit()

    project = await _get_project_with_envs(db, project.id)
    env = project.environments[0]

    for _ in range(5):
        await record_evaluation(db, flag.id, env.id)
    await db.commit()

    result = await db.execute(
        select(UsageRecord).where(
            UsageRecord.flag_id == flag.id,
            UsageRecord.environment_id == env.id,
        )
    )
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].evaluation_count == 5


async def test_record_evaluation_separate_envs(db: AsyncSession):
    """Different environments should have separate usage records."""
    user = await create_user(db, "usage3@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Usage Project", user.id)
    flag = await create_flag(db, project.id, "test_flag", flag_type="boolean")
    await db.commit()

    project = await _get_project_with_envs(db, project.id)
    envs = project.environments

    await record_evaluation(db, flag.id, envs[0].id)
    await record_evaluation(db, flag.id, envs[0].id)
    await record_evaluation(db, flag.id, envs[1].id)
    await db.commit()

    result = await db.execute(
        select(UsageRecord).where(UsageRecord.flag_id == flag.id)
    )
    records = result.scalars().all()
    assert len(records) == 2
    counts = sorted([r.evaluation_count for r in records])
    assert counts == [1, 2]


async def test_get_usage_for_project(db: AsyncSession):
    """get_usage_for_project should return all records for the project."""
    user = await create_user(db, "usage4@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Usage Project", user.id)
    flag1 = await create_flag(db, project.id, "flag_one", flag_type="boolean")
    flag2 = await create_flag(db, project.id, "flag_two", flag_type="string")
    await db.commit()

    project = await _get_project_with_envs(db, project.id)
    env = project.environments[0]

    await record_evaluation(db, flag1.id, env.id)
    await record_evaluation(db, flag2.id, env.id)
    await record_evaluation(db, flag2.id, env.id)
    await db.commit()

    records = await get_usage_for_project(db, project.id)
    assert len(records) == 2
    total = sum(r.evaluation_count for r in records)
    assert total == 3


async def test_get_total_evaluations_for_project(db: AsyncSession):
    """get_total_evaluations_for_project should sum all evaluation counts."""
    user = await create_user(db, "usage5@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Usage Project", user.id)
    flag = await create_flag(db, project.id, "test_flag", flag_type="boolean")
    await db.commit()

    project = await _get_project_with_envs(db, project.id)
    env = project.environments[0]

    for _ in range(10):
        await record_evaluation(db, flag.id, env.id)
    await db.commit()

    total = await get_total_evaluations_for_project(db, project.id)
    assert total == 10


async def test_get_total_evaluations_empty_project(db: AsyncSession):
    """Empty projects should return 0 evaluations."""
    user = await create_user(db, "usage6@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Empty Project", user.id)
    await db.commit()

    total = await get_total_evaluations_for_project(db, project.id)
    assert total == 0


async def test_usage_separate_flags(db: AsyncSession):
    """Each flag should track usage independently."""
    user = await create_user(db, "usage7@example.com", "testpass123", "Usage User")
    project = await create_project(db, "Usage Project", user.id)
    flag1 = await create_flag(db, project.id, "alpha", flag_type="boolean")
    flag2 = await create_flag(db, project.id, "beta", flag_type="boolean")
    await db.commit()

    project = await _get_project_with_envs(db, project.id)
    env = project.environments[0]

    for _ in range(3):
        await record_evaluation(db, flag1.id, env.id)
    for _ in range(7):
        await record_evaluation(db, flag2.id, env.id)
    await db.commit()

    total = await get_total_evaluations_for_project(db, project.id)
    assert total == 10
