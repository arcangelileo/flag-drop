import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.environment import Environment
from app.models.project import Project

DEFAULT_ENVIRONMENTS = [
    {"name": "Development", "slug": "development", "color": "#22C55E", "sort_order": 0},
    {"name": "Staging", "slug": "staging", "color": "#F59E0B", "sort_order": 1},
    {"name": "Production", "slug": "production", "color": "#EF4444", "sort_order": 2},
]


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-")


async def create_project(
    db: AsyncSession,
    name: str,
    owner_id: str,
    description: str | None = None,
) -> Project:
    slug = slugify(name)

    # Ensure slug uniqueness for this owner
    base_slug = slug
    counter = 1
    while True:
        existing = await db.execute(
            select(Project).where(Project.slug == slug, Project.owner_id == owner_id)
        )
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    project = Project(name=name, slug=slug, description=description, owner_id=owner_id)
    db.add(project)
    await db.flush()

    # Auto-create default environments
    for env_data in DEFAULT_ENVIRONMENTS:
        env = Environment(project_id=project.id, **env_data)
        db.add(env)
    await db.flush()

    await db.refresh(project)
    return project


async def get_projects_for_user(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user_id)
        .options(selectinload(Project.flags), selectinload(Project.environments))
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project_by_id(
    db: AsyncSession, project_id: str, owner_id: str
) -> Project | None:
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.owner_id == owner_id)
        .options(
            selectinload(Project.flags),
            selectinload(Project.environments),
            selectinload(Project.api_keys),
        )
    )
    return result.scalar_one_or_none()


async def update_project(
    db: AsyncSession,
    project: Project,
    name: str | None = None,
    description: str | None = None,
) -> Project:
    if name is not None:
        project.name = name
        project.slug = slugify(name)
    if description is not None:
        project.description = description
    await db.flush()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    await db.delete(project)
    await db.flush()
