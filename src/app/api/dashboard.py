from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.services.projects import get_project_by_id
from app.services.usage import get_usage_for_project, get_total_evaluations_for_project

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

    # Calculate stats
    total_flags = sum(len(p.flags) for p in projects)
    total_envs = sum(len(p.environments) for p in projects)

    # Get total evaluations across all projects (last 30 days)
    total_evaluations = 0
    project_evaluations = {}
    for project in projects:
        evals = await get_total_evaluations_for_project(db, project.id, days=30)
        total_evaluations += evals
        project_evaluations[project.id] = evals

    return templates.TemplateResponse(
        request, "dashboard/index.html",
        {
            "user": user,
            "projects": projects,
            "active_nav": "dashboard",
            "total_flags": total_flags,
            "total_envs": total_envs,
            "total_evaluations": total_evaluations,
            "project_evaluations": project_evaluations,
        },
    )


@router.get("/projects/{project_id}/usage", response_class=HTMLResponse)
async def project_usage_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Get usage records for last 30 days
    usage_records = await get_usage_for_project(db, project_id, days=30)
    total_evaluations = await get_total_evaluations_for_project(db, project_id, days=30)

    # Aggregate by day for chart
    from datetime import date, timedelta
    from collections import defaultdict

    daily_totals = defaultdict(int)
    flag_totals = defaultdict(int)
    defaultdict(int)

    for record in usage_records:
        daily_totals[record.record_date.isoformat()] += record.evaluation_count
        if record.flag:
            flag_totals[record.flag.name] += record.evaluation_count

    # Build last 14 days for chart
    today = date.today()
    chart_days = []
    chart_values = []
    max_value = 1
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        val = daily_totals.get(d.isoformat(), 0)
        chart_days.append(d.strftime("%b %d"))
        chart_values.append(val)
        if val > max_value:
            max_value = val

    # Sort flags by usage
    top_flags = sorted(flag_totals.items(), key=lambda x: x[1], reverse=True)[:10]

    return templates.TemplateResponse(
        request, "dashboard/usage.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "active_nav": "usage",
            "total_evaluations": total_evaluations,
            "chart_days": chart_days,
            "chart_values": chart_values,
            "max_value": max_value,
            "top_flags": top_flags,
            "total_flags": len(project.flags),
        },
    )
