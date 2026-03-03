"""Tests for Environments management."""


async def _create_project(db, user_id):
    from app.services.projects import create_project
    project = await create_project(db, "Env Test Project", user_id)
    await db.commit()
    return project


async def test_environments_page(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.get(f"/projects/{project.id}/environments")
    assert response.status_code == 200
    assert "Environments" in response.text
    assert "Development" in response.text
    assert "Staging" in response.text
    assert "Production" in response.text


async def test_environments_page_requires_auth(client, db):
    response = await client.get("/projects/fake-id/environments", follow_redirects=False)
    # Should redirect to login or 401
    assert response.status_code in (302, 401)


async def test_create_custom_environment(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/environments", data={
        "name": "QA",
        "color": "#8B5CF6",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "success" in response.headers["location"]

    # Verify it appears in the list
    response = await client.get(f"/projects/{project.id}/environments")
    assert "QA" in response.text


async def test_create_environment_empty_name(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    response = await client.post(f"/projects/{project.id}/environments", data={
        "name": "",
        "color": "#8B5CF6",
    })
    assert response.status_code == 400
    assert "required" in response.text


async def test_delete_environment(authenticated_client, db):
    client, user = authenticated_client
    project = await _create_project(db, user.id)

    from app.services.environments import get_environments_for_project
    envs = await get_environments_for_project(db, project.id)
    env_to_delete = envs[0]

    response = await client.post(
        f"/projects/{project.id}/environments/{env_to_delete.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 302

    # Verify it's gone
    envs_after = await get_environments_for_project(db, project.id)
    env_ids = {e.id for e in envs_after}
    assert env_to_delete.id not in env_ids


async def test_environments_wrong_project(authenticated_client, db):
    client, user = authenticated_client

    response = await client.get("/projects/nonexistent-id/environments", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"
