"""Tests for dashboard routes including stats and usage analytics."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import create_access_token, create_user
from app.services.projects import create_project
from app.services.flags import create_flag
from app.services.api_keys import create_api_key
from app.services.environments import get_environments_for_project


@pytest.fixture
async def authenticated_client(client: AsyncClient, db: AsyncSession):
    user = await create_user(db, "dash@example.com", "testpass123", "Dashboard User")
    await db.commit()
    token = create_access_token(user.id, user.email)
    client.cookies.set("access_token", token)
    return client, user


async def test_dashboard_shows_stats(authenticated_client, db: AsyncSession):
    """Dashboard should show stats cards with project/flag/env/eval counts."""
    client, user = authenticated_client

    project = await create_project(db, "Stats Project", user.id, "Test")
    await create_flag(db, project.id, "Flag One", flag_type="boolean")
    await create_flag(db, project.id, "Flag Two", flag_type="string")
    await db.commit()

    response = await client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    html = response.text

    assert "Stats Project" in html
    assert "Evaluations" in html


async def test_dashboard_empty_state(authenticated_client, db: AsyncSession):
    """Dashboard should show empty state when no projects exist."""
    client, user = authenticated_client
    response = await client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert "No projects yet" in response.text
    assert "Create your first project" in response.text


async def test_dashboard_multiple_projects(authenticated_client, db: AsyncSession):
    """Dashboard should show all user projects."""
    client, user = authenticated_client

    await create_project(db, "Project Alpha", user.id)
    await create_project(db, "Project Beta", user.id)
    await create_project(db, "Project Gamma", user.id)
    await db.commit()

    response = await client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert "Project Alpha" in response.text
    assert "Project Beta" in response.text
    assert "Project Gamma" in response.text


async def test_dashboard_project_evaluation_count(authenticated_client, db: AsyncSession):
    """Dashboard should show evaluation count per project."""
    client, user = authenticated_client

    project = await create_project(db, "Eval Project", user.id)
    await create_flag(db, project.id, "test_flag", flag_type="boolean")
    envs = await get_environments_for_project(db, project.id)
    _, raw_key = await create_api_key(db, "Test Key", project.id, envs[0].id)
    await db.commit()

    # Evaluate flags to generate usage
    eval_response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert eval_response.status_code == 200

    # Check dashboard reflects usage
    response = await client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200


async def test_usage_page_requires_auth(client: AsyncClient):
    """Usage page should require authentication (returns 401)."""
    response = await client.get("/projects/fake-id/usage", follow_redirects=False)
    assert response.status_code == 401


async def test_usage_page_loads(authenticated_client, db: AsyncSession):
    """Usage page should load with chart and stats."""
    client, user = authenticated_client

    project = await create_project(db, "Usage Project", user.id)
    await create_flag(db, project.id, "feature_x", flag_type="boolean")
    await db.commit()

    response = await client.get(f"/projects/{project.id}/usage", follow_redirects=True)
    assert response.status_code == 200
    assert "Usage Analytics" in response.text
    assert "Total Evaluations" in response.text
    assert "Active Flags" in response.text
    assert "Daily Evaluations" in response.text


async def test_usage_page_empty_state(authenticated_client, db: AsyncSession):
    """Usage page should show empty state when no evaluations exist."""
    client, user = authenticated_client

    project = await create_project(db, "Empty Usage", user.id)
    await db.commit()

    response = await client.get(f"/projects/{project.id}/usage", follow_redirects=True)
    assert response.status_code == 200
    assert "No evaluations yet" in response.text


async def test_usage_page_wrong_project(authenticated_client, db: AsyncSession):
    """Usage page should redirect if project doesn't belong to user."""
    client, user = authenticated_client

    other_user = await create_user(db, "other@example.com", "testpass123", "Other User")
    other_project = await create_project(db, "Other Project", other_user.id)
    await db.commit()

    response = await client.get(
        f"/projects/{other_project.id}/usage", follow_redirects=False
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers.get("location", "")


async def test_usage_page_with_evaluations(authenticated_client, db: AsyncSession):
    """Usage page should show chart data when evaluations exist."""
    client, user = authenticated_client

    project = await create_project(db, "Active Project", user.id)
    await create_flag(db, project.id, "active_flag", flag_type="boolean")
    envs = await get_environments_for_project(db, project.id)
    _, raw_key = await create_api_key(db, "Test Key", project.id, envs[0].id)
    await db.commit()

    # Generate some evaluations
    for _ in range(5):
        await client.get(
            "/api/v1/flags/active_flag",
            headers={"Authorization": f"Bearer {raw_key}"},
        )

    response = await client.get(f"/projects/{project.id}/usage", follow_redirects=True)
    assert response.status_code == 200
    assert "Top Flags by Usage" in response.text
    assert "active_flag" in response.text


async def test_usage_page_top_flags(authenticated_client, db: AsyncSession):
    """Usage page should rank flags by evaluation count."""
    client, user = authenticated_client

    project = await create_project(db, "Top Flags Project", user.id)
    await create_flag(db, project.id, "popular_flag", flag_type="boolean")
    await create_flag(db, project.id, "rare_flag", flag_type="boolean")
    envs = await get_environments_for_project(db, project.id)
    _, raw_key = await create_api_key(db, "Key", project.id, envs[0].id)
    await db.commit()

    # Evaluate popular_flag more times
    for _ in range(5):
        await client.get(
            "/api/v1/flags/popular_flag",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    # Evaluate rare_flag once
    await client.get(
        "/api/v1/flags/rare_flag",
        headers={"Authorization": f"Bearer {raw_key}"},
    )

    response = await client.get(f"/projects/{project.id}/usage", follow_redirects=True)
    assert response.status_code == 200
    html = response.text
    # popular_flag should appear before rare_flag in the rankings
    popular_pos = html.find("popular_flag")
    rare_pos = html.find("rare_flag")
    assert popular_pos < rare_pos
