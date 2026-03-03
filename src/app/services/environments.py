import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environment import Environment


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")


async def get_environments_for_project(
    db: AsyncSession, project_id: str
) -> list[Environment]:
    result = await db.execute(
        select(Environment)
        .where(Environment.project_id == project_id)
        .order_by(Environment.sort_order)
    )
    return list(result.scalars().all())


async def get_environment_by_id(
    db: AsyncSession, environment_id: str, project_id: str
) -> Environment | None:
    result = await db.execute(
        select(Environment).where(
            Environment.id == environment_id,
            Environment.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def create_environment(
    db: AsyncSession,
    project_id: str,
    name: str,
    color: str = "#6B7280",
) -> Environment:
    slug = slugify(name)

    # Get next sort_order
    result = await db.execute(
        select(func.max(Environment.sort_order)).where(
            Environment.project_id == project_id
        )
    )
    max_order = result.scalar() or 0

    env = Environment(
        name=name,
        slug=slug,
        color=color,
        sort_order=max_order + 1,
        project_id=project_id,
    )
    db.add(env)
    await db.flush()
    await db.refresh(env)
    return env


async def delete_environment(db: AsyncSession, environment: Environment) -> None:
    await db.delete(environment)
    await db.flush()
