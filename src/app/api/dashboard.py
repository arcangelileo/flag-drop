from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user_optional
from app.database import get_db
from app.models.project import Project
from app.models.user import User

router = APIRouter(tags=["dashboard"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    result = await db.execute(
        select(Project)
        .where(Project.owner_id == user.id)
        .options(selectinload(Project.flags), selectinload(Project.environments))
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    return templates.TemplateResponse(
        request, "dashboard/index.html",
        {"user": user, "projects": projects, "active_nav": "dashboard"},
    )
