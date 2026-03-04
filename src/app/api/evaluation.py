import json

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.api_key import APIKey
from app.models.flag import Flag
from app.models.flag_value import FlagValue
from app.services.api_keys import get_api_key_by_raw_key, update_last_used
from app.services.usage import record_evaluation

router = APIRouter(prefix="/api/v1", tags=["evaluation"])


async def get_api_key_from_header(
    authorization: str | None = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Extract and validate an API key from the Authorization: Bearer header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Authorization: Bearer <api_key>",
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format. Use: Authorization: Bearer <api_key>",
        )

    raw_key = parts[1].strip()
    api_key = await get_api_key_by_raw_key(db, raw_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )

    await update_last_used(db, api_key)
    return api_key


@router.get("/flags")
async def evaluate_all_flags(
    api_key: APIKey = Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate all flags for the project+environment associated with this API key."""
    result = await db.execute(
        select(Flag)
        .where(Flag.project_id == api_key.project_id)
        .options(selectinload(Flag.flag_values))
    )
    flags = result.scalars().all()

    response_flags = {}
    for flag in flags:
        # Find the value for this API key's environment
        flag_value = None
        for fv in flag.flag_values:
            if fv.environment_id == api_key.environment_id:
                flag_value = fv
                break

        if flag_value:
            enabled = flag_value.enabled
            try:
                value = json.loads(flag_value.value)
            except (json.JSONDecodeError, TypeError):
                value = flag_value.value
        else:
            enabled = False
            try:
                value = json.loads(flag.default_value)
            except (json.JSONDecodeError, TypeError):
                value = flag.default_value

        response_flags[flag.key] = {
            "key": flag.key,
            "enabled": enabled,
            "value": value,
            "type": flag.flag_type,
        }

        # Record usage for all flags
        await record_evaluation(db, flag.id, api_key.environment_id)

    return {
        "flags": response_flags,
        "environment": api_key.environment.slug if api_key.environment else None,
        "project": api_key.project.slug if api_key.project else None,
    }


@router.get("/flags/{flag_key}")
async def evaluate_single_flag(
    flag_key: str,
    api_key: APIKey = Depends(get_api_key_from_header),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate a single flag by key for the project+environment associated with this API key."""
    result = await db.execute(
        select(Flag)
        .where(Flag.project_id == api_key.project_id, Flag.key == flag_key)
        .options(selectinload(Flag.flag_values))
    )
    flag = result.scalar_one_or_none()

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flag '{flag_key}' not found.",
        )

    # Find value for this environment
    flag_value = None
    for fv in flag.flag_values:
        if fv.environment_id == api_key.environment_id:
            flag_value = fv
            break

    if flag_value:
        enabled = flag_value.enabled
        try:
            value = json.loads(flag_value.value)
        except (json.JSONDecodeError, TypeError):
            value = flag_value.value
    else:
        enabled = False
        try:
            value = json.loads(flag.default_value)
        except (json.JSONDecodeError, TypeError):
            value = flag.default_value

    # Record usage
    await record_evaluation(db, flag.id, api_key.environment_id)

    return {
        "key": flag.key,
        "enabled": enabled,
        "value": value,
        "type": flag.flag_type,
    }
