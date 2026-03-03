from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.environments import (
    create_environment,
    delete_environment,
    get_environment_by_id,
    get_environments_for_project,
)
from app.services.projects import get_project_by_id

router = APIRouter(prefix="/projects/{project_id}/environments", tags=["environments"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("", response_class=HTMLResponse)
async def environments_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    environments = await get_environments_for_project(db, project_id)

    return templates.TemplateResponse(
        request, "environments/list.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "environments": environments,
            "active_nav": "environments",
            "success": request.query_params.get("success"),
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_environment_handler(
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
    color = form.get("color", "#6B7280").strip()

    environments = await get_environments_for_project(db, project_id)

    if not name:
        return templates.TemplateResponse(
            request, "environments/list.html",
            {
                "user": user,
                "project": project,
                "current_project": project,
                "environments": environments,
                "error": "Environment name is required.",
                "active_nav": "environments",
            },
            status_code=400,
        )

    if len(name) > 100:
        return templates.TemplateResponse(
            request, "environments/list.html",
            {
                "user": user,
                "project": project,
                "current_project": project,
                "environments": environments,
                "error": "Environment name must be under 100 characters.",
                "active_nav": "environments",
            },
            status_code=400,
        )

    await create_environment(db, project_id, name, color)
    return RedirectResponse(
        url=f"/projects/{project_id}/environments?success=Environment+created",
        status_code=302,
    )


@router.post("/{environment_id}/delete")
async def delete_environment_handler(
    request: Request,
    project_id: str,
    environment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    environment = await get_environment_by_id(db, environment_id, project_id)
    if not environment:
        return RedirectResponse(
            url=f"/projects/{project_id}/environments", status_code=302
        )

    await delete_environment(db, environment)
    return RedirectResponse(
        url=f"/projects/{project_id}/environments?success=Environment+deleted",
        status_code=302,
    )
