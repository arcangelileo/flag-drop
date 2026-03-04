from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.api_keys import (
    create_api_key,
    delete_api_key,
    get_api_key_by_id,
    get_api_keys_for_project,
    revoke_api_key,
)
from app.services.audit import log_action
from app.services.environments import get_environments_for_project
from app.services.projects import get_project_by_id

router = APIRouter(prefix="/projects/{project_id}/api-keys", tags=["api_keys"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("", response_class=HTMLResponse)
async def api_keys_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    api_keys = await get_api_keys_for_project(db, project_id)
    environments = await get_environments_for_project(db, project_id)

    return templates.TemplateResponse(
        request, "api_keys/list.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "api_keys": api_keys,
            "environments": environments,
            "active_nav": "api_keys",
            "success": request.query_params.get("success"),
            "created_key": request.query_params.get("created_key"),
            "created_name": request.query_params.get("created_name"),
        },
    )


@router.post("")
async def create_api_key_handler(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    form = await request.form()
    name = form.get("name", "").strip()
    environment_id = form.get("environment_id", "").strip()

    api_keys = await get_api_keys_for_project(db, project_id)
    environments = await get_environments_for_project(db, project_id)

    if not name:
        return templates.TemplateResponse(
            request, "api_keys/list.html",
            {
                "user": user,
                "project": project,
                "current_project": project,
                "api_keys": api_keys,
                "environments": environments,
                "error": "API key name is required.",
                "active_nav": "api_keys",
            },
            status_code=400,
        )

    if not environment_id:
        return templates.TemplateResponse(
            request, "api_keys/list.html",
            {
                "user": user,
                "project": project,
                "current_project": project,
                "api_keys": api_keys,
                "environments": environments,
                "error": "Please select an environment.",
                "active_nav": "api_keys",
            },
            status_code=400,
        )

    api_key, raw_key = await create_api_key(db, name, project_id, environment_id)

    await log_action(
        db,
        action="created",
        entity_type="api_key",
        entity_id=api_key.id,
        project_id=project_id,
        user_id=user.id,
        new_value={"name": name, "key_prefix": api_key.key_prefix},
    )

    # Redirect with the raw key shown once
    from urllib.parse import quote
    return RedirectResponse(
        url=f"/projects/{project_id}/api-keys?created_key={quote(raw_key)}&created_name={quote(name)}",
        status_code=303,
    )


@router.post("/{api_key_id}/revoke")
async def revoke_api_key_handler(
    request: Request,
    project_id: str,
    api_key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    api_key = await get_api_key_by_id(db, api_key_id, project_id)
    if not api_key:
        return RedirectResponse(url=f"/projects/{project_id}/api-keys", status_code=302)

    await revoke_api_key(db, api_key)

    await log_action(
        db,
        action="revoked",
        entity_type="api_key",
        entity_id=api_key.id,
        project_id=project_id,
        user_id=user.id,
        old_value={"name": api_key.name, "key_prefix": api_key.key_prefix},
    )

    return RedirectResponse(
        url=f"/projects/{project_id}/api-keys?success=API+key+revoked",
        status_code=303,
    )


@router.post("/{api_key_id}/delete")
async def delete_api_key_handler(
    request: Request,
    project_id: str,
    api_key_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    api_key = await get_api_key_by_id(db, api_key_id, project_id)
    if not api_key:
        return RedirectResponse(url=f"/projects/{project_id}/api-keys", status_code=302)

    await log_action(
        db,
        action="deleted",
        entity_type="api_key",
        entity_id=api_key.id,
        project_id=project_id,
        user_id=user.id,
        old_value={"name": api_key.name, "key_prefix": api_key.key_prefix},
    )

    await delete_api_key(db, api_key)

    return RedirectResponse(
        url=f"/projects/{project_id}/api-keys?success=API+key+deleted",
        status_code=303,
    )
