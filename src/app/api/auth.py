from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.database import get_db
from app.models.user import User
from app.services.auth import authenticate_user, create_access_token, create_user, get_user_by_email

router = APIRouter(tags=["auth"])

templates = Jinja2Templates(directory="src/app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(
        request, "auth/login.html",
        {"error": request.query_params.get("error")},
    )


@router.post("/login")
async def login(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    email = form.get("email", "").strip()
    password = form.get("password", "")

    if not email or not password:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Email and password are required.", "email": email},
            status_code=400,
        )

    user = await authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            request, "auth/login.html",
            {"error": "Invalid email or password.", "email": email},
            status_code=401,
        )

    token = create_access_token(user.id, user.email)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
        secure=False,
    )
    return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request, "auth/signup.html")


@router.post("/signup")
async def signup(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    email = form.get("email", "").strip()
    password = form.get("password", "")
    confirm_password = form.get("confirm_password", "")
    full_name = form.get("full_name", "").strip()

    errors = []
    if not email:
        errors.append("Email is required.")
    if not full_name:
        errors.append("Full name is required.")
    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return templates.TemplateResponse(
            request, "auth/signup.html",
            {"errors": errors, "email": email, "full_name": full_name},
            status_code=400,
        )

    existing = await get_user_by_email(db, email)
    if existing:
        return templates.TemplateResponse(
            request, "auth/signup.html",
            {"errors": ["An account with this email already exists."], "email": email, "full_name": full_name},
            status_code=409,
        )

    user = await create_user(db, email, password, full_name)
    token = create_access_token(user.id, user.email)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
        secure=False,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/api/auth/me")
async def me(user: User = Depends(get_current_user_optional)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
    }
