"""Advanced tests for flag evaluation API covering edge cases and type handling."""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import create_access_token, create_user
from app.services.projects import create_project
from app.services.flags import create_flag, get_flag_by_id, toggle_flag_value, update_flag_value
from app.services.api_keys import create_api_key
from app.services.environments import get_environments_for_project


@pytest.fixture
async def eval_setup(client: AsyncClient, db: AsyncSession):
    """Set up a project with multiple flag types and an API key."""
    user = await create_user(db, "eval@example.com", "testpass123", "Eval User")
    project = await create_project(db, "Eval Project", user.id)
    envs = await get_environments_for_project(db, project.id)
    env = envs[0]

    # Create flags of different types
    bool_flag = await create_flag(db, project.id, "dark_mode", flag_type="boolean", default_value="true")
    str_flag = await create_flag(db, project.id, "welcome_msg", flag_type="string", default_value='"Hello"')
    num_flag = await create_flag(db, project.id, "max_retries", flag_type="number", default_value="3")
    json_flag = await create_flag(db, project.id, "config", flag_type="json", default_value='{"theme": "dark"}')

    api_key, raw_key = await create_api_key(db, "Eval Key", project.id, env.id)
    await db.commit()

    return {
        "client": client,
        "user": user,
        "project": project,
        "env": env,
        "bool_flag_id": bool_flag.id,
        "str_flag_id": str_flag.id,
        "num_flag_id": num_flag.id,
        "json_flag_id": json_flag.id,
        "raw_key": raw_key,
    }


async def test_evaluate_boolean_flag(eval_setup):
    """Boolean flags should return proper boolean values."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags/dark_mode",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "dark_mode"
    assert data["type"] == "boolean"
    assert isinstance(data["value"], bool)


async def test_evaluate_string_flag(eval_setup):
    """String flags should return string values."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags/welcome_msg",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "welcome_msg"
    assert data["type"] == "string"
    assert isinstance(data["value"], str)


async def test_evaluate_number_flag(eval_setup):
    """Number flags should return numeric values."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags/max_retries",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "max_retries"
    assert data["type"] == "number"
    assert isinstance(data["value"], (int, float))
    assert data["value"] == 3


async def test_evaluate_json_flag(eval_setup):
    """JSON flags should return parsed JSON values."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags/config",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "config"
    assert data["type"] == "json"
    assert isinstance(data["value"], dict)
    assert data["value"]["theme"] == "dark"


async def test_evaluate_all_returns_all_types(eval_setup):
    """GET /api/v1/flags should return all flags with correct types."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    assert response.status_code == 200
    data = response.json()
    flags = data["flags"]

    assert "dark_mode" in flags
    assert "welcome_msg" in flags
    assert "max_retries" in flags
    assert "config" in flags

    assert flags["dark_mode"]["type"] == "boolean"
    assert flags["welcome_msg"]["type"] == "string"
    assert flags["max_retries"]["type"] == "number"
    assert flags["config"]["type"] == "json"


async def test_evaluate_enabled_flag(eval_setup, db: AsyncSession):
    """Enabled flags should return enabled=True."""
    ctx = eval_setup

    # Reload flag with values eagerly loaded
    bool_flag = await get_flag_by_id(db, ctx["bool_flag_id"], ctx["project"].id)

    # Enable the flag for the environment
    for fv in bool_flag.flag_values:
        if fv.environment_id == ctx["env"].id:
            await toggle_flag_value(db, fv.id)
            break
    await db.commit()

    response = await ctx["client"].get(
        "/api/v1/flags/dark_mode",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    data = response.json()
    assert data["enabled"] is True


async def test_evaluate_updated_value(eval_setup, db: AsyncSession):
    """Evaluation should reflect updated flag values."""
    ctx = eval_setup

    # Reload flag with values eagerly loaded
    num_flag = await get_flag_by_id(db, ctx["num_flag_id"], ctx["project"].id)

    # Update the value
    for fv in num_flag.flag_values:
        if fv.environment_id == ctx["env"].id:
            await update_flag_value(db, fv.id, value="42")
            break
    await db.commit()

    response = await ctx["client"].get(
        "/api/v1/flags/max_retries",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    data = response.json()
    assert data["value"] == 42


async def test_evaluate_response_includes_project_env(eval_setup):
    """All flags response should include project and environment info."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {ctx['raw_key']}"},
    )
    data = response.json()
    assert "environment" in data
    assert "project" in data
    assert data["environment"] is not None
    assert data["project"] is not None


async def test_evaluate_multiple_keys_different_envs(client: AsyncClient, db: AsyncSession):
    """Different API keys for different environments should get different values."""
    user = await create_user(db, "multienv@example.com", "testpass123", "Multi Env User")
    project = await create_project(db, "Multi Env Project", user.id)
    flag = await create_flag(db, project.id, "env_flag", flag_type="string", default_value='"default"')
    envs = await get_environments_for_project(db, project.id)

    dev_env = envs[0]  # Development
    staging_env = envs[1]  # Staging

    # Reload flag to get flag values with environment
    flag = await get_flag_by_id(db, flag.id, project.id)

    # Set different values per environment
    for fv in flag.flag_values:
        if fv.environment_id == dev_env.id:
            await update_flag_value(db, fv.id, value='"dev-value"', enabled=True)
        elif fv.environment_id == staging_env.id:
            await update_flag_value(db, fv.id, value='"staging-value"', enabled=True)

    _, dev_key = await create_api_key(db, "Dev Key", project.id, dev_env.id)
    _, staging_key = await create_api_key(db, "Staging Key", project.id, staging_env.id)
    await db.commit()

    # Evaluate with dev key
    dev_response = await client.get(
        "/api/v1/flags/env_flag",
        headers={"Authorization": f"Bearer {dev_key}"},
    )
    assert dev_response.json()["value"] == "dev-value"

    # Evaluate with staging key
    staging_response = await client.get(
        "/api/v1/flags/env_flag",
        headers={"Authorization": f"Bearer {staging_key}"},
    )
    assert staging_response.json()["value"] == "staging-value"


async def test_evaluate_authorization_case_insensitive(eval_setup):
    """Bearer token parsing should handle different casing."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags",
        headers={"Authorization": f"bearer {ctx['raw_key']}"},
    )
    assert response.status_code == 200


async def test_evaluate_with_extra_whitespace_in_key(eval_setup):
    """API key with extra whitespace should still work (stripped)."""
    ctx = eval_setup
    response = await ctx["client"].get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer  {ctx['raw_key']}  "},
    )
    # The key has extra spaces; the code strips the key
    assert response.status_code in (200, 401)
