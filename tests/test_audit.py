"""Tests for the audit log system."""


async def _setup_project(db, user_id):
    from app.services.projects import create_project
    project = await create_project(db, "Audit Test Project", user_id)
    await db.commit()
    return project


async def test_audit_log_page_empty(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    response = await client.get(f"/projects/{project.id}/audit-log")
    assert response.status_code == 200
    assert "Audit Log" in response.text
    assert "No activity yet" in response.text


async def test_audit_log_page_requires_auth(client):
    response = await client.get("/projects/fake/audit-log", follow_redirects=False)
    assert response.status_code in (302, 401)


async def test_audit_log_records_flag_creation(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    # Create a flag via the web UI
    await client.post(f"/projects/{project.id}/flags/new", data={
        "name": "Audit Flag",
        "key": "audit_flag",
        "flag_type": "boolean",
    }, follow_redirects=False)

    # Check audit log
    response = await client.get(f"/projects/{project.id}/audit-log")
    assert response.status_code == 200
    assert "created" in response.text
    assert "Audit Flag" in response.text or "audit_flag" in response.text


async def test_audit_log_records_flag_toggle(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Toggle Audit", key="toggle_audit")
    await db.commit()

    from sqlalchemy import select
    from app.models.flag_value import FlagValue
    result = await db.execute(select(FlagValue).where(FlagValue.flag_id == flag.id))
    fv = result.scalars().first()

    await client.post(
        f"/projects/{project.id}/flags/{flag.id}/toggle/{fv.id}",
        follow_redirects=False,
    )

    response = await client.get(f"/projects/{project.id}/audit-log")
    assert response.status_code == 200
    assert "toggled" in response.text


async def test_audit_log_records_flag_delete(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.flags import create_flag
    flag = await create_flag(db, project.id, "Delete Audit", key="delete_audit")
    await db.commit()

    await client.post(
        f"/projects/{project.id}/flags/{flag.id}/delete",
        follow_redirects=False,
    )

    response = await client.get(f"/projects/{project.id}/audit-log")
    assert response.status_code == 200
    # Should show both create (from service) + delete entries
    assert "deleted" in response.text


async def test_audit_log_records_api_key_creation(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.environments import get_environments_for_project
    envs = await get_environments_for_project(db, project.id)

    await client.post(f"/projects/{project.id}/api-keys", data={
        "name": "Audit API Key",
        "environment_id": envs[0].id,
    }, follow_redirects=False)

    response = await client.get(f"/projects/{project.id}/audit-log")
    assert response.status_code == 200
    assert "API key" in response.text


async def test_audit_log_service(db):
    from app.models.user import User
    from app.models.project import Project
    from app.services.audit import log_action, get_audit_logs_for_project, count_audit_logs_for_project

    user = User(email="audit@test.com", hashed_password="h", full_name="Audit")
    db.add(user)
    await db.flush()

    project = Project(name="AuditP", slug="auditp", owner_id=user.id)
    db.add(project)
    await db.flush()

    await log_action(db, "created", "flag", "flag-123", project.id, user.id,
                     new_value={"name": "test"})
    await log_action(db, "updated", "flag", "flag-123", project.id, user.id,
                     old_value={"name": "test"}, new_value={"name": "test2"})
    await log_action(db, "deleted", "flag", "flag-123", project.id, user.id,
                     old_value={"name": "test2"})

    logs = await get_audit_logs_for_project(db, project.id)
    assert len(logs) == 3

    count = await count_audit_logs_for_project(db, project.id)
    assert count == 3


async def test_audit_log_pagination(authenticated_client, db):
    client, user = authenticated_client
    project = await _setup_project(db, user.id)

    from app.services.audit import log_action
    for i in range(30):
        await log_action(db, "created", "flag", f"flag-{i}", project.id, user.id)
    await db.commit()

    # First page
    response = await client.get(f"/projects/{project.id}/audit-log?page=1")
    assert response.status_code == 200
    assert "Page 1" in response.text
    assert "Next" in response.text

    # Second page
    response = await client.get(f"/projects/{project.id}/audit-log?page=2")
    assert response.status_code == 200
    assert "Page 2" in response.text
    assert "Previous" in response.text


async def test_audit_log_wrong_project(authenticated_client, db):
    client, user = authenticated_client

    response = await client.get("/projects/nonexistent/audit-log", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"
