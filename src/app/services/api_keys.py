from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.api_key import APIKey
from app.models.environment import Environment
from app.services.auth import generate_api_key, hash_api_key


async def create_api_key(
    db: AsyncSession,
    name: str,
    project_id: str,
    environment_id: str,
) -> tuple[APIKey, str]:
    """Create a new API key. Returns (api_key_model, raw_key).
    The raw_key is only available at creation time."""
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = APIKey(
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        project_id=project_id,
        environment_id=environment_id,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)
    return api_key, raw_key


async def get_api_keys_for_project(
    db: AsyncSession, project_id: str
) -> list[APIKey]:
    result = await db.execute(
        select(APIKey)
        .where(APIKey.project_id == project_id)
        .options(selectinload(APIKey.environment))
        .order_by(APIKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_api_key_by_id(
    db: AsyncSession, api_key_id: str, project_id: str
) -> APIKey | None:
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == api_key_id,
            APIKey.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def revoke_api_key(db: AsyncSession, api_key: APIKey) -> None:
    api_key.is_active = False
    await db.flush()


async def delete_api_key(db: AsyncSession, api_key: APIKey) -> None:
    await db.delete(api_key)
    await db.flush()


async def get_api_key_by_raw_key(
    db: AsyncSession, raw_key: str
) -> APIKey | None:
    """Look up an API key by its raw value (hashes it first)."""
    key_hash = hash_api_key(raw_key)
    result = await db.execute(
        select(APIKey)
        .where(APIKey.key_hash == key_hash, APIKey.is_active == True)  # noqa: E712
        .options(selectinload(APIKey.environment), selectinload(APIKey.project))
    )
    return result.scalar_one_or_none()


async def update_last_used(db: AsyncSession, api_key: APIKey) -> None:
    from datetime import datetime, timezone
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()
