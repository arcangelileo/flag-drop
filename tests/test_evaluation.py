"""Tests for the flag evaluation API (GET /api/v1/flags)."""


async def _setup_project_with_flags(db, user_id):
    """Create a project with flags and an API key, return (project, api_key_raw, envs)."""
    from app.services.projects import create_project
    from app.services.flags import create_flag
    from app.services.api_keys import create_api_key
    from app.services.environments import get_environments_for_project

    project = await create_project(db, "Eval Test Project", user_id)
    envs = await get_environments_for_project(db, project.id)

    # Create flags
    flag1 = await create_flag(db, project.id, "Dark Mode", key="dark_mode", flag_type="boolean")
    await create_flag(db, project.id, "Banner Text", key="banner_text", flag_type="string", default_value='"Hello"')
    await create_flag(db, project.id, "Max Items", key="max_items", flag_type="number", default_value="10")

    # Toggle dark_mode ON for first environment
    from sqlalchemy import select
    from app.models.flag_value import FlagValue

    result = await db.execute(
        select(FlagValue).where(
            FlagValue.flag_id == flag1.id,
            FlagValue.environment_id == envs[0].id,
        )
    )
    fv = result.scalar_one()
    fv.enabled = True
    fv.value = "true"

    # Create API key for first environment
    api_key, raw_key = await create_api_key(db, "Test Key", project.id, envs[0].id)
    await db.commit()

    return project, raw_key, envs


async def test_evaluate_all_flags(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "flags" in data
    assert "dark_mode" in data["flags"]
    assert data["flags"]["dark_mode"]["enabled"] is True
    assert data["flags"]["dark_mode"]["value"] is True
    assert data["flags"]["dark_mode"]["type"] == "boolean"
    assert "banner_text" in data["flags"]
    assert "max_items" in data["flags"]
    assert data["environment"] is not None
    assert data["project"] is not None


async def test_evaluate_single_flag(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    response = await client.get(
        "/api/v1/flags/dark_mode",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "dark_mode"
    assert data["enabled"] is True
    assert data["value"] is True
    assert data["type"] == "boolean"


async def test_evaluate_disabled_flag(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    response = await client.get(
        "/api/v1/flags/banner_text",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "banner_text"
    assert data["enabled"] is False


async def test_evaluate_nonexistent_flag(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    response = await client.get(
        "/api/v1/flags/nonexistent_flag",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


async def test_evaluate_no_auth(client):
    response = await client.get("/api/v1/flags")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


async def test_evaluate_invalid_auth(client):
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": "Bearer invalid_key_here"},
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


async def test_evaluate_bad_auth_format(client):
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": "NotBearer abc123"},
    )
    assert response.status_code == 401


async def test_evaluate_revoked_key(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    from app.services.api_keys import get_api_key_by_raw_key, revoke_api_key
    api_key = await get_api_key_by_raw_key(db, raw_key)
    await revoke_api_key(db, api_key)
    await db.commit()

    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 401


async def test_evaluate_records_usage(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    # Make several evaluations
    await client.get("/api/v1/flags/dark_mode", headers={"Authorization": f"Bearer {raw_key}"})
    await client.get("/api/v1/flags/dark_mode", headers={"Authorization": f"Bearer {raw_key}"})
    await client.get("/api/v1/flags/dark_mode", headers={"Authorization": f"Bearer {raw_key}"})

    from sqlalchemy import select
    from app.models.usage_record import UsageRecord
    from app.models.flag import Flag

    result = await db.execute(select(Flag).where(Flag.key == "dark_mode", Flag.project_id == project.id))
    flag = result.scalar_one()

    result = await db.execute(
        select(UsageRecord).where(UsageRecord.flag_id == flag.id)
    )
    records = result.scalars().all()
    assert len(records) > 0
    total = sum(r.evaluation_count for r in records)
    assert total >= 3


async def test_evaluate_all_flags_records_usage(authenticated_client, db):
    client, user = authenticated_client
    project, raw_key, envs = await _setup_project_with_flags(db, user.id)

    response = await client.get("/api/v1/flags", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 200

    from sqlalchemy import select, func
    from app.models.usage_record import UsageRecord
    result = await db.execute(select(func.count(UsageRecord.id)))
    count = result.scalar()
    assert count > 0  # At least some usage was recorded
