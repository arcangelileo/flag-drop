from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.projects import (
    create_project,
    delete_project,
    get_project_by_id,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("/new", response_class=HTMLResponse)
async def new_project_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "projects/new.html",
        {"user": user, "active_nav": "dashboard"},
    )


@router.post("/new")
async def create_project_handler(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()

    errors = []
    if not name:
        errors.append("Project name is required.")
    elif len(name) > 255:
        errors.append("Project name must be under 255 characters.")

    if errors:
        return templates.TemplateResponse(
            request, "projects/new.html",
            {"user": user, "errors": errors, "name": name, "description": description, "active_nav": "dashboard"},
            status_code=400,
        )

    project = await create_project(db, name, user.id, description or None)
    return RedirectResponse(url=f"/projects/{project.id}/flags", status_code=303)


@router.get("/{project_id}/settings", response_class=HTMLResponse)
async def project_settings_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request, "projects/settings.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "active_nav": "settings",
            "success": request.query_params.get("success"),
        },
    )


@router.post("/{project_id}/settings")
async def update_project_handler(
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
    description = form.get("description", "").strip()

    errors = []
    if not name:
        errors.append("Project name is required.")

    if errors:
        return templates.TemplateResponse(
            request, "projects/settings.html",
            {
                "user": user,
                "project": project,
                "current_project": project,
                "errors": errors,
                "active_nav": "settings",
            },
            status_code=400,
        )

    await update_project(db, project, name=name, description=description or None)
    return RedirectResponse(
        url=f"/projects/{project_id}/settings?success=Project+updated+successfully",
        status_code=303,
    )


@router.post("/{project_id}/delete")
async def delete_project_handler(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    await delete_project(db, project)
    return RedirectResponse(url="/dashboard", status_code=303)
