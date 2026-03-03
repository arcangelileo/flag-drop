from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.environments import router as environments_router
from app.api.flags import router as flags_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Feature flag management platform for development teams",
    lifespan=lifespan,
)

# Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(projects_router)
app.include_router(environments_router)
app.include_router(flags_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/login", status_code=302)
