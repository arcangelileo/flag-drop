"""Tests for Flags CRUD and flag values."""


async def _create_project(db, user_id):
    from app.services.projects import create_project
    project = await create_project(db, "Flag Test Project", user_id)
    await db.commit()
    return project


async def test_flags_page_empty(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.get(f"/projects/{project.id}/flags")
    assert response.status_code == 200
    assert "No flags yet" in response.text


async def test_new_flag_page(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.get(f"/projects/{project.id}/flags/new")
    assert response.status_code == 200
    assert "Create a new flag" in response.text
    assert "Boolean" in response.text
    assert "String" in response.text


async def test_create_flag_boolean(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/flags/new", data={
        "name": "Dark Mode",
        "key": "dark_mode",
        "flag_type": "boolean",
        "description": "Enable dark mode",
        "default_value": "false",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "success" in response.headers["location"]


async def test_create_flag_string(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/flags/new", data={
        "name": "Banner Text",
        "key": "banner_text",
        "flag_type": "string",
        "description": "Homepage banner text",
        "default_value": '"Welcome!"',
    }, follow_redirects=False)
    assert response.status_code == 302


async def test_create_flag_missing_name(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/flags/new", data={
        "name": "",
        "key": "",
        "flag_type": "boolean",
    })
    assert response.status_code == 400
    assert "required" in response.text


async def test_create_flag_invalid_type(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/flags/new", data={
        "name": "Test",
        "key": "test",
        "flag_type": "invalid_type",
    })
    assert response.status_code == 400
    assert "Invalid flag type" in response.text


async def test_create_flag_auto_creates_values(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    await client.post(f"/projects/{project.id}/flags/new", data={
        "name": "Feature X",
        "key": "feature_x",
        "flag_type": "boolean",
    }, follow_redirects=False)

    from sqlalchemy import select
    from app.models.flag import Flag
    from app.models.flag_value import FlagValue

    result = await db.execute(select(Flag).where(Flag.project_id == project.id))
    flag = result.scalar_one()

    result = await db.execute(select(FlagValue).where(FlagValue.flag_id == flag.id))
    values = result.scalars().all()
    # Should have 3 values (one per default environment)
    assert len(values) == 3
    # All should be disabled by default
    assert all(not fv.enabled for fv in values)


async def test_flag_detail_page(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Detail Flag", key="detail_flag")
    await db.commit()

    response = await client.get(f"/projects/{project.id}/flags/{flag.id}")
    assert response.status_code == 200
    assert "Detail Flag" in response.text
    assert "detail_flag" in response.text
    assert "Development" in response.text
    assert "Staging" in response.text
    assert "Production" in response.text


async def test_update_flag(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Old Flag Name", key="old_flag")
    await db.commit()

    response = await client.post(f"/projects/{project.id}/flags/{flag.id}/edit", data={
        "name": "New Flag Name",
        "description": "Updated description",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "success" in response.headers["location"]


async def test_delete_flag(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Delete Flag", key="delete_flag")
    await db.commit()

    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "success" in response.headers["location"]

    # Verify deleted
    from sqlalchemy import select
    from app.models.flag import Flag
    result = await db.execute(select(Flag).where(Flag.id == flag.id))
    assert result.scalar_one_or_none() is None


async def test_toggle_flag_value(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Toggle Flag", key="toggle_flag")
    await db.commit()

    from sqlalchemy import select
    from app.models.flag_value import FlagValue

    result = await db.execute(select(FlagValue).where(FlagValue.flag_id == flag.id))
    fv = result.scalars().first()
    assert fv is not None
    assert fv.enabled is False

    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/toggle/{fv.id}",
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db.refresh(fv)
    assert fv.enabled is True


async def test_update_flag_value(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Val Flag", key="val_flag", flag_type="string", default_value='"old"')
    await db.commit()

    from sqlalchemy import select
    from app.models.flag_value import FlagValue

    result = await db.execute(select(FlagValue).where(FlagValue.flag_id == flag.id))
    fv = result.scalars().first()

    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/values/{fv.id}",
        data={"value": '"new_value"'},
        follow_redirects=False,
    )
    assert response.status_code == 302

    await db.refresh(fv)
    assert fv.value == '"new_value"'


async def test_flags_list_shows_flags(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.flags import create_flag
    await create_flag(db, project.id, "Listed Flag", key="listed_flag")
    await db.commit()

    response = await client.get(f"/projects/{project.id}/flags")
    assert response.status_code == 200
    assert "Listed Flag" in response.text
    assert "listed_flag" in response.text


async def test_flag_detail_wrong_project(authenticated_client, db):
    client, user = authenticated_client

    response = await client.get(
        "/projects/nonexistent-id/flags/fake-flag-id",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


# --- Service-level tests ---


async def test_slugify_key():
    from app.services.flags import slugify_key
    assert slugify_key("Dark Mode") == "dark_mode"
    assert slugify_key("Banner Text  Setting") == "banner_text_setting"
    assert slugify_key("API Key v2") == "api_key_v2"


async def test_validate_flag_value_boolean():
    from app.services.flags import validate_flag_value
    assert validate_flag_value("boolean", "true") is None
    assert validate_flag_value("boolean", "false") is None
    assert validate_flag_value("boolean", '"hello"') is not None


async def test_validate_flag_value_number():
    from app.services.flags import validate_flag_value
    assert validate_flag_value("number", "42") is None
    assert validate_flag_value("number", "3.14") is None
    assert validate_flag_value("number", '"text"') is not None


async def test_validate_flag_value_string():
    from app.services.flags import validate_flag_value
    assert validate_flag_value("string", '"hello"') is None
    assert validate_flag_value("string", "42") is not None


async def test_validate_flag_value_json():
    from app.services.flags import validate_flag_value
    assert validate_flag_value("json", '{"key": "value"}') is None
    assert validate_flag_value("json", "not json at all") is not None


async def test_project_slugify():
    from app.services.projects import slugify
    assert slugify("My App") == "my-app"
    assert slugify("Hello World 123") == "hello-world-123"
    assert slugify("  Spaced  Out  ") == "spaced-out"
