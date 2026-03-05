import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.audit import log_action
from app.services.environments import get_environments_for_project
from app.services.flags import (
    VALID_FLAG_TYPES,
    create_flag,
    delete_flag,
    get_flag_by_id,
    get_flags_for_project,
    slugify_key,
    toggle_flag_value,
    update_flag,
    update_flag_value,
    validate_flag_value,
)
from app.services.projects import get_project_by_id

router = APIRouter(prefix="/projects/{project_id}/flags", tags=["flags"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("", response_class=HTMLResponse)
async def flags_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    flags = await get_flags_for_project(db, project_id)
    environments = await get_environments_for_project(db, project_id)

    return templates.TemplateResponse(
        request, "flags/list.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "flags": flags,
            "environments": environments,
            "active_nav": "flags",
            "success": request.query_params.get("success"),
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_flag_page(
    request: Request,
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        request, "flags/new.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "active_nav": "flags",
            "flag_types": VALID_FLAG_TYPES,
        },
    )


@router.post("/new")
async def create_flag_handler(
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
    key = form.get("key", "").strip()
    flag_type = form.get("flag_type", "boolean")
    description = form.get("description", "").strip()
    default_value = form.get("default_value", "").strip()

    if not key and name:
        key = slugify_key(name)

    errors = []
    if not name:
        errors.append("Flag name is required.")
    elif len(name) > 255:
        errors.append("Flag name must be under 255 characters.")
    if not key:
        errors.append("Flag key is required.")
    elif not re.match(r'^[a-z0-9_]+$', key):
        errors.append("Flag key must contain only lowercase letters, numbers, and underscores.")
    if flag_type not in VALID_FLAG_TYPES:
        errors.append(f"Invalid flag type. Must be one of: {', '.join(VALID_FLAG_TYPES)}")

    if default_value:
        val_err = validate_flag_value(flag_type, default_value)
        if val_err:
            errors.append(val_err)

    if errors:
        return templates.TemplateResponse(
            request, "flags/new.html",
            {
                "user": user,
                "project": project,
                "current_project": project,
                "errors": errors,
                "name": name,
                "key": key,
                "flag_type": flag_type,
                "description": description,
                "default_value": default_value,
                "active_nav": "flags",
                "flag_types": VALID_FLAG_TYPES,
            },
            status_code=400,
        )

    flag = await create_flag(
        db, project_id, name,
        key=key,
        flag_type=flag_type,
        default_value=default_value or None,
        description=description or None,
    )

    await log_action(
        db, action="created", entity_type="flag", entity_id=flag.id,
        project_id=project_id, user_id=user.id, flag_id=flag.id,
        new_value={"name": name, "key": key, "type": flag_type},
    )

    return RedirectResponse(
        url=f"/projects/{project_id}/flags?success=Flag+created+successfully",
        status_code=303,
    )


@router.get("/{flag_id}", response_class=HTMLResponse)
async def flag_detail_page(
    request: Request,
    project_id: str,
    flag_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    flag = await get_flag_by_id(db, flag_id, project_id)
    if not flag:
        return RedirectResponse(url=f"/projects/{project_id}/flags", status_code=302)

    environments = await get_environments_for_project(db, project_id)

    env_values = {}
    for fv in flag.flag_values:
        env_values[fv.environment_id] = fv

    return templates.TemplateResponse(
        request, "flags/detail.html",
        {
            "user": user,
            "project": project,
            "current_project": project,
            "flag": flag,
            "environments": environments,
            "env_values": env_values,
            "active_nav": "flags",
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/{flag_id}/edit")
async def update_flag_handler(
    request: Request,
    project_id: str,
    flag_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    flag = await get_flag_by_id(db, flag_id, project_id)
    if not flag:
        return RedirectResponse(url=f"/projects/{project_id}/flags", status_code=302)

    form = await request.form()
    name = form.get("name", "").strip()
    description = form.get("description", "").strip()

    if not name:
        return RedirectResponse(
            url=f"/projects/{project_id}/flags/{flag_id}?error=Flag+name+is+required",
            status_code=303,
        )

    old_name = flag.name
    old_desc = flag.description
    await update_flag(db, flag, name=name, description=description or None)

    await log_action(
        db, action="updated", entity_type="flag", entity_id=flag.id,
        project_id=project_id, user_id=user.id, flag_id=flag.id,
        old_value={"name": old_name, "description": old_desc},
        new_value={"name": name, "description": description or None},
    )

    return RedirectResponse(
        url=f"/projects/{project_id}/flags/{flag_id}?success=Flag+updated",
        status_code=303,
    )


@router.post("/{flag_id}/delete")
async def delete_flag_handler(
    request: Request,
    project_id: str,
    flag_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    flag = await get_flag_by_id(db, flag_id, project_id)
    if not flag:
        return RedirectResponse(url=f"/projects/{project_id}/flags", status_code=302)

    await log_action(
        db, action="deleted", entity_type="flag", entity_id=flag.id,
        project_id=project_id, user_id=user.id,
        old_value={"name": flag.name, "key": flag.key, "type": flag.flag_type},
    )

    await delete_flag(db, flag)
    return RedirectResponse(
        url=f"/projects/{project_id}/flags?success=Flag+deleted",
        status_code=303,
    )


@router.post("/{flag_id}/toggle/{flag_value_id}")
async def toggle_flag_handler(
    request: Request,
    project_id: str,
    flag_id: str,
    flag_value_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    flag = await get_flag_by_id(db, flag_id, project_id)
    if not flag:
        return RedirectResponse(url=f"/projects/{project_id}/flags", status_code=303)

    fv = await toggle_flag_value(db, flag_value_id, flag_id=flag_id)
    if not fv:
        return RedirectResponse(
            url=f"/projects/{project_id}/flags/{flag_id}", status_code=302
        )

    await log_action(
        db, action="toggled", entity_type="flag_value", entity_id=fv.id,
        project_id=project_id, user_id=user.id,
        flag_id=flag.id,
        old_value={"enabled": not fv.enabled},
        new_value={"enabled": fv.enabled, "environment_id": fv.environment_id},
    )

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            _render_toggle_button(project_id, flag_id, fv.id, fv.enabled)
        )

    return RedirectResponse(
        url=f"/projects/{project_id}/flags/{flag_id}?success=Flag+toggled",
        status_code=303,
    )


@router.post("/{flag_id}/values/{flag_value_id}")
async def update_flag_value_handler(
    request: Request,
    project_id: str,
    flag_id: str,
    flag_value_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project_by_id(db, project_id, user.id)
    if not project:
        return RedirectResponse(url="/dashboard", status_code=302)

    form = await request.form()
    value = form.get("value", "").strip()

    flag = await get_flag_by_id(db, flag_id, project_id)
    if not flag:
        return RedirectResponse(url=f"/projects/{project_id}/flags", status_code=302)

    if value:
        val_err = validate_flag_value(flag.flag_type, value)
        if val_err:
            from urllib.parse import quote
            return RedirectResponse(
                url=f"/projects/{project_id}/flags/{flag_id}?error={quote(val_err)}",
                status_code=303,
            )

    # Find old value for audit
    old_val = None
    for fv in flag.flag_values:
        if fv.id == flag_value_id:
            old_val = fv.value
            break

    await update_flag_value(db, flag_value_id, value=value, flag_id=flag_id)

    await log_action(
        db, action="updated", entity_type="flag_value", entity_id=flag_value_id,
        project_id=project_id, user_id=user.id, flag_id=flag.id,
        old_value={"value": old_val},
        new_value={"value": value},
    )

    return RedirectResponse(
        url=f"/projects/{project_id}/flags/{flag_id}?success=Value+updated",
        status_code=303,
    )


def _render_toggle_button(
    project_id: str, flag_id: str, fv_id: str, enabled: bool
) -> str:
    color_on = "bg-brand-600"
    color_off = "bg-gray-300"
    translate_on = "translate-x-5"
    translate_off = "translate-x-0"

    bg = color_on if enabled else color_off
    translate = translate_on if enabled else translate_off
    label = "On" if enabled else "Off"

    return f"""
    <form hx-post="/projects/{project_id}/flags/{flag_id}/toggle/{fv_id}"
          hx-swap="outerHTML"
          hx-target="closest form"
          class="inline-flex items-center space-x-2">
        <button type="submit"
                class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 {bg}"
                role="switch" aria-checked="{'true' if enabled else 'false'}"
                aria-label="Toggle flag {'on' if enabled else 'off'}">
            <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {translate}"></span>
        </button>
        <span class="text-sm font-medium {'text-brand-600' if enabled else 'text-gray-500'}">{label}</span>
    </form>
    """
