from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.audit import count_audit_logs_for_project, get_audit_logs_for_project
from app.services.projects import get_project_by_id

router = APIRouter(prefix="/projects/{project_id}/audit-log", tags=["audit"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("", response_class=HTMLResponse)
async def audit_log_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 25
    offset = (page - 1) * per_page

    logs = await get_audit_logs_for_project(db, project_id, limit=per_page, offset=offset)
    total = await count_audit_logs_for_project(db, project_id)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request, "audit/list.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "logs": logs,
            "active_nav": "audit_log",
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )
