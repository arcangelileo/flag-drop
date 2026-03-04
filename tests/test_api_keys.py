"""Tests for API key management."""


async def _setup_project(db, user_id):
    from app.services.projects import create_project
    project = await create_project(db, "API Key Test Project", user_id)
    await db.commit()
    return project


async def test_api_keys_page(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    response = await client.get(f"/projects/{project.id}/api-keys")
    assert response.status_code == 200
    assert "API Keys" in response.text
    assert "No API keys yet" in response.text


async def test_api_keys_page_requires_auth(client):
    response = await client.get("/projects/fake/api-keys", follow_redirects=False)
    assert response.status_code in (302, 401)


async def test_create_api_key(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    envs = await get_environments_for_project(db, project.id)

    response = await client.post(f"/projects/{project.id}/api-keys", data={
        "name": "Production Server",
        "environment_id": envs[0].id,
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "created_key=" in response.headers["location"]
    assert "created_name=" in response.headers["location"]


async def test_create_api_key_shows_key_once(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    envs = await get_environments_for_project(db, project.id)

    # POST returns a redirect with the raw key in the URL
    response = await client.post(f"/projects/{project.id}/api-keys", data={
        "name": "My Key",
        "environment_id": envs[0].id,
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    redirect_url = response.headers["location"]
    assert "created_key=fd_" in redirect_url

    # Follow the redirect to see the key displayed
    response = await client.get(redirect_url)
    assert response.status_code == 200
    assert "fd_" in response.text


async def test_create_api_key_empty_name(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    envs = await get_environments_for_project(db, project.id)

    response = await client.post(f"/projects/{project.id}/api-keys", data={
        "name": "",
        "environment_id": envs[0].id,
    })
    assert response.status_code == 400
    assert "required" in response.text


async def test_create_api_key_no_environment(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/api-keys", data={
        "name": "My Key",
        "environment_id": "",
    })
    assert response.status_code == 400
    assert "environment" in response.text.lower()


async def test_revoke_api_key(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    from app.services.api_keys import create_api_key
    envs = await get_environments_for_project(db, project.id)
    api_key, raw_key = await create_api_key(db, "Revoke Test", project.id, envs[0].id)
    await db.commit()

    response = await client.post(
        f"/projects/{project.id}/api-keys/{api_key.id}/revoke",
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "revoked" in response.headers["location"].lower()

    await db.refresh(api_key)
    assert api_key.is_active is False


async def test_delete_api_key(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    from app.services.api_keys import create_api_key
    envs = await get_environments_for_project(db, project.id)
    api_key, raw_key = await create_api_key(db, "Delete Test", project.id, envs[0].id)
    await db.commit()

    response = await client.post(
        f"/projects/{project.id}/api-keys/{api_key.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)

    from sqlalchemy import select
    from app.models.api_key import APIKey
    result = await db.execute(select(APIKey).where(APIKey.id == api_key.id))
    assert result.scalar_one_or_none() is None


async def test_api_keys_list_shows_keys(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    from app.services.api_keys import create_api_key
    envs = await get_environments_for_project(db, project.id)
    await create_api_key(db, "Listed Key", project.id, envs[0].id)
    await db.commit()

    response = await client.get(f"/projects/{project.id}/api-keys")
    assert response.status_code == 200
    assert "Listed Key" in response.text
    assert "Active" in response.text
