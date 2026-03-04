"""Integration tests covering full user workflows end-to-end."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import create_access_token, create_user
from app.services.projects import create_project
from app.services.flags import create_flag, get_flag_by_id
from app.services.api_keys import create_api_key
from app.services.environments import get_environments_for_project


@pytest.fixture
async def authenticated_client(client: AsyncClient, db: AsyncSession):
    user = await create_user(db, "integration@example.com", "testpass123", "Integration User")
    await db.commit()
    token = create_access_token(user.id, user.email)
    client.cookies.set("access_token", token)
    return client, user


async def test_full_workflow_create_project_flags_evaluate(client: AsyncClient, db: AsyncSession):
    """Full workflow: signup -> create project -> create flag -> get API key -> evaluate."""
    # 1. Sign up
    response = await client.post(
        "/signup",
        data={
            "email": "workflow@example.com",
            "password": "securepass123",
            "confirm_password": "securepass123",
            "full_name": "Workflow User",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "access_token" in response.cookies

    # 2. Create project
    response = await client.post(
        "/projects/new",
        data={"name": "My App", "description": "Test application"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    project_url = response.headers["location"]
    project_id = project_url.split("/projects/")[1].split("/")[0]

    # 3. Create flag
    response = await client.post(
        f"/projects/{project_id}/flags/new",
        data={
            "name": "New Feature",
            "key": "new_feature",
            "flag_type": "boolean",
            "default_value": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # 4. Get environments to find one for API key
    response = await client.get(f"/projects/{project_id}/environments", follow_redirects=True)
    assert response.status_code == 200
    assert "Development" in response.text

    # 5. Create API key using service to get env id
    envs = await get_environments_for_project(db, project_id)
    dev_env = envs[0]

    response = await client.post(
        f"/projects/{project_id}/api-keys",
        data={"name": "Workflow Key", "environment_id": dev_env.id},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    location = response.headers["location"]
    assert "created_key=" in location

    # Extract the raw key from the redirect URL
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(location)
    raw_key = parse_qs(parsed.query)["created_key"][0]

    # 6. Evaluate flags via API
    eval_response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert eval_response.status_code == 200
    data = eval_response.json()
    assert "new_feature" in data["flags"]
    assert data["flags"]["new_feature"]["type"] == "boolean"

    # 7. Check audit log shows the flag creation
    response = await client.get(f"/projects/{project_id}/audit-log", follow_redirects=True)
    assert response.status_code == 200
    assert "created" in response.text.lower()

    # 8. Check usage page
    response = await client.get(f"/projects/{project_id}/usage", follow_redirects=True)
    assert response.status_code == 200
    assert "Usage Analytics" in response.text


async def test_project_isolation(client: AsyncClient, db: AsyncSession):
    """Different users should not see each other's projects or flags."""
    user1 = await create_user(db, "user1@example.com", "testpass123", "User One")
    user2 = await create_user(db, "user2@example.com", "testpass123", "User Two")

    project1 = await create_project(db, "User1 Project", user1.id)
    project2 = await create_project(db, "User2 Project", user2.id)
    await create_flag(db, project1.id, "flag_one", flag_type="boolean")
    await create_flag(db, project2.id, "flag_two", flag_type="boolean")
    await db.commit()

    token1 = create_access_token(user1.id, user1.email)
    client.cookies.set("access_token", token1)

    response = await client.get("/dashboard", follow_redirects=True)
    assert "User1 Project" in response.text
    assert "User2 Project" not in response.text

    response = await client.get(
        f"/projects/{project2.id}/flags", follow_redirects=False
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["location"]


async def test_flag_toggle_and_evaluate(authenticated_client, db: AsyncSession):
    """Toggle a flag and verify the evaluation API reflects the change."""
    client, user = authenticated_client

    project = await create_project(db, "Toggle Project", user.id)
    flag = await create_flag(db, project.id, "toggle_test", flag_type="boolean", default_value="false")
    envs = await get_environments_for_project(db, project.id)
    _, raw_key = await create_api_key(db, "Toggle Key", project.id, envs[0].id)
    await db.commit()

    # Initially disabled
    response = await client.get(
        "/api/v1/flags/toggle_test",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.json()["enabled"] is False

    # Reload flag with values eagerly loaded
    flag = await get_flag_by_id(db, flag.id, project.id)
    flag_value_id = None
    for fv in flag.flag_values:
        if fv.environment_id == envs[0].id:
            flag_value_id = fv.id
            break

    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/toggle/{flag_value_id}",
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # Now should be enabled
    response = await client.get(
        "/api/v1/flags/toggle_test",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.json()["enabled"] is True


async def test_delete_project_cascades(authenticated_client, db: AsyncSession):
    """Deleting a project should remove all associated data."""
    client, user = authenticated_client

    project = await create_project(db, "Delete Project", user.id)
    await create_flag(db, project.id, "doomed_flag", flag_type="boolean")
    envs = await get_environments_for_project(db, project.id)
    _, raw_key = await create_api_key(db, "Doomed Key", project.id, envs[0].id)
    await db.commit()

    project_id = project.id

    # Verify flag evaluation works before deletion
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200

    # Delete the project
    response = await client.post(
        f"/projects/{project_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # API key should no longer work
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 401


async def test_flag_value_update_and_evaluate(authenticated_client, db: AsyncSession):
    """Update a flag value and verify evaluation returns the new value."""
    client, user = authenticated_client

    project = await create_project(db, "Value Project", user.id)
    flag = await create_flag(db, project.id, "greeting", flag_type="string", default_value='"Hello"')
    envs = await get_environments_for_project(db, project.id)
    _, raw_key = await create_api_key(db, "Value Key", project.id, envs[0].id)
    await db.commit()

    # Reload flag to get flag values with environment
    flag = await get_flag_by_id(db, flag.id, project.id)
    flag_value_id = None
    for fv in flag.flag_values:
        if fv.environment_id == envs[0].id:
            flag_value_id = fv.id
            break

    # Update the value
    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/values/{flag_value_id}",
        data={"value": '"Goodbye"'},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # Evaluate should return new value
    response = await client.get(
        "/api/v1/flags/greeting",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.json()["value"] == "Goodbye"


async def test_create_number_and_json_flags(authenticated_client, db: AsyncSession):
    """Test creating number and JSON type flags via the web UI."""
    client, user = authenticated_client

    project = await create_project(db, "Types Project", user.id)
    await db.commit()

    # Create number flag
    response = await client.post(
        f"/projects/{project.id}/flags/new",
        data={
            "name": "Rate Limit",
            "key": "rate_limit",
            "flag_type": "number",
            "default_value": "100",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # Create JSON flag
    response = await client.post(
        f"/projects/{project.id}/flags/new",
        data={
            "name": "Feature Config",
            "key": "feature_config",
            "flag_type": "json",
            "default_value": '{"enabled": true, "limit": 50}',
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # Verify flags appear in list
    response = await client.get(
        f"/projects/{project.id}/flags", follow_redirects=True
    )
    assert response.status_code == 200
    assert "Rate Limit" in response.text
    assert "Feature Config" in response.text
    assert "number" in response.text
    assert "json" in response.text


async def test_revoked_key_cannot_evaluate(authenticated_client, db: AsyncSession):
    """Revoking an API key should immediately prevent flag evaluation."""
    client, user = authenticated_client

    project = await create_project(db, "Revoke Project", user.id)
    await create_flag(db, project.id, "test_flag", flag_type="boolean")
    envs = await get_environments_for_project(db, project.id)
    api_key, raw_key = await create_api_key(db, "Revoke Key", project.id, envs[0].id)
    await db.commit()

    # Key works before revoking
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200

    # Revoke the key via the UI
    response = await client.post(
        f"/projects/{project.id}/api-keys/{api_key.id}/revoke",
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    # Key should no longer work
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 401
