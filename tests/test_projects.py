"""Tests for Projects CRUD."""


async def test_new_project_page_requires_auth(client):
    response = await client.get("/projects/new", follow_redirects=False)
    assert response.status_code == 401 or response.status_code == 302


async def test_new_project_page(authenticated_client):
    client, user = authenticated_client
    response = await client.get("/projects/new")
    assert response.status_code == 200
    assert "Create a new project" in response.text


async def test_create_project(authenticated_client):
    client, user = authenticated_client
    response = await client.post("/projects/new", data={
        "name": "My Test App",
        "description": "A test application",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/flags" in response.headers["location"]


async def test_create_project_missing_name(authenticated_client):
    client, user = authenticated_client
    response = await client.post("/projects/new", data={
        "name": "",
        "description": "No name",
    })
    assert response.status_code == 400
    assert "required" in response.text


async def test_create_project_auto_creates_environments(authenticated_client, db):
    client, user = authenticated_client

    response = await client.post("/projects/new", data={
        "name": "Env Test App",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)

    # Check that environments were created
    from sqlalchemy import select
    from app.models.environment import Environment
    from app.models.project import Project

    result = await db.execute(select(Project).where(Project.owner_id == user.id))
    project = result.scalar_one()

    result = await db.execute(
        select(Environment).where(Environment.project_id == project.id)
    )
    envs = result.scalars().all()
    assert len(envs) == 3
    env_names = {e.name for e in envs}
    assert env_names == {"Development", "Staging", "Production"}


async def test_project_settings_page(authenticated_client, db):
    client, user = authenticated_client

    # Create a project first
    from app.services.projects import create_project
    project = await create_project(db, "Settings Test", user.id)
    await db.commit()

    response = await client.get(f"/projects/{project.id}/settings")
    assert response.status_code == 200
    assert "Settings Test" in response.text
    assert "Danger Zone" in response.text


async def test_update_project(authenticated_client, db):
    client, user = authenticated_client

    from app.services.projects import create_project
    project = await create_project(db, "Old Name", user.id, "Old desc")
    await db.commit()

    response = await client.post(f"/projects/{project.id}/settings", data={
        "name": "New Name",
        "description": "New description",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "success" in response.headers["location"]


async def test_update_project_empty_name(authenticated_client, db):
    client, user = authenticated_client

    from app.services.projects import create_project
    project = await create_project(db, "My Project", user.id)
    await db.commit()

    response = await client.post(f"/projects/{project.id}/settings", data={
        "name": "",
        "description": "",
    })
    assert response.status_code == 400
    assert "required" in response.text


async def test_delete_project(authenticated_client, db):
    client, user = authenticated_client

    from app.services.projects import create_project
    project = await create_project(db, "Delete Me", user.id)
    await db.commit()

    response = await client.post(f"/projects/{project.id}/delete", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/dashboard"

    # Verify deleted
    from sqlalchemy import select
    from app.models.project import Project
    result = await db.execute(select(Project).where(Project.id == project.id))
    assert result.scalar_one_or_none() is None


async def test_project_settings_wrong_owner(authenticated_client, db):
    """Test that a user can't access another user's project settings."""
    client, user = authenticated_client

    from app.models.project import Project
    other_project = Project(name="Other", slug="other", owner_id="nonexistent-user")
    db.add(other_project)
    await db.flush()
    await db.commit()

    response = await client.get(f"/projects/{other_project.id}/settings", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


async def test_dashboard_shows_projects(authenticated_client, db):
    client, user = authenticated_client

    from app.services.projects import create_project
    await create_project(db, "Dashboard Project", user.id, "A project for dashboard")
    await db.commit()

    response = await client.get("/dashboard")
    assert response.status_code == 200
    assert "Dashboard Project" in response.text
