import json
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.environment import Environment
from app.models.flag import Flag
from app.models.flag_value import FlagValue


def slugify_key(value: str) -> str:
    """Convert a name to a flag key (snake_case)."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "_", value).strip("_")


VALID_FLAG_TYPES = {"boolean", "string", "number", "json"}

DEFAULT_VALUES = {
    "boolean": "false",
    "string": '""',
    "number": "0",
    "json": "{}",
}


def validate_flag_value(flag_type: str, value: str) -> str | None:
    """Validate a flag value matches its type. Returns error message or None."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return f"Invalid JSON value: {value}"

    if flag_type == "boolean" and not isinstance(parsed, bool):
        return "Boolean flags must have a value of true or false."
    if flag_type == "number" and not isinstance(parsed, (int, float)):
        return "Number flags must have a numeric value."
    if flag_type == "string" and not isinstance(parsed, str):
        return "String flags must have a text value."
    return None


async def get_flags_for_project(
    db: AsyncSession, project_id: str
) -> list[Flag]:
    result = await db.execute(
        select(Flag)
        .where(Flag.project_id == project_id)
        .options(selectinload(Flag.flag_values).selectinload(FlagValue.environment))
        .order_by(Flag.created_at.desc())
    )
    return list(result.scalars().all())


async def get_flag_by_id(
    db: AsyncSession, flag_id: str, project_id: str
) -> Flag | None:
    result = await db.execute(
        select(Flag)
        .where(Flag.id == flag_id, Flag.project_id == project_id)
        .options(selectinload(Flag.flag_values).selectinload(FlagValue.environment))
    )
    return result.scalar_one_or_none()


async def create_flag(
    db: AsyncSession,
    project_id: str,
    name: str,
    key: str | None = None,
    flag_type: str = "boolean",
    default_value: str | None = None,
    description: str | None = None,
) -> Flag:
    if not key:
        key = slugify_key(name)

    if not default_value:
        default_value = DEFAULT_VALUES.get(flag_type, "false")

    flag = Flag(
        key=key,
        name=name,
        description=description,
        flag_type=flag_type,
        default_value=default_value,
        project_id=project_id,
    )
    db.add(flag)
    await db.flush()

    # Auto-create flag values for each environment
    envs_result = await db.execute(
        select(Environment).where(Environment.project_id == project_id)
    )
    environments = envs_result.scalars().all()

    for env in environments:
        fv = FlagValue(
            flag_id=flag.id,
            environment_id=env.id,
            enabled=False,
            value=default_value,
        )
        db.add(fv)
    await db.flush()

    await db.refresh(flag)
    return flag


async def update_flag(
    db: AsyncSession,
    flag: Flag,
    name: str | None = None,
    description: str | None = None,
    default_value: str | None = None,
) -> Flag:
    if name is not None:
        flag.name = name
    if description is not None:
        flag.description = description
    if default_value is not None:
        flag.default_value = default_value
    await db.flush()
    await db.refresh(flag)
    return flag


async def delete_flag(db: AsyncSession, flag: Flag) -> None:
    await db.delete(flag)
    await db.flush()


async def toggle_flag_value(
    db: AsyncSession, flag_value_id: str, flag_id: str | None = None
) -> FlagValue | None:
    query = select(FlagValue).where(FlagValue.id == flag_value_id)
    if flag_id:
        query = query.where(FlagValue.flag_id == flag_id)
    result = await db.execute(query)
    fv = result.scalar_one_or_none()
    if not fv:
        return None
    fv.enabled = not fv.enabled
    await db.flush()
    await db.refresh(fv)
    return fv


async def update_flag_value(
    db: AsyncSession,
    flag_value_id: str,
    value: str | None = None,
    enabled: bool | None = None,
    flag_id: str | None = None,
) -> FlagValue | None:
    query = select(FlagValue).where(FlagValue.id == flag_value_id)
    if flag_id:
        query = query.where(FlagValue.flag_id == flag_id)
    result = await db.execute(query)
    fv = result.scalar_one_or_none()
    if not fv:
        return None
    if value is not None:
        fv.value = value
    if enabled is not None:
        fv.enabled = enabled
    await db.flush()
    await db.refresh(fv)
    return fv


async def get_flag_value(
    db: AsyncSession, flag_id: str, environment_id: str
) -> FlagValue | None:
    result = await db.execute(
        select(FlagValue).where(
            FlagValue.flag_id == flag_id,
            FlagValue.environment_id == environment_id,
        )
    )
    return result.scalar_one_or_none()
