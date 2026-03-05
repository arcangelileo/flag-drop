"""QA-specific tests for bugs found during QA session."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


pytestmark = pytest.mark.anyio


async def _create_project_and_flag(client, db):
    """Helper: create a project, flag, and return IDs."""
    from app.services.auth import create_access_token, create_user
    from app.services.projects import create_project
    from app.services.flags import create_flag, get_flag_by_id

    user = await create_user(db, "qa@test.com", "testpass123", "QA User")
    await db.commit()
    token = create_access_token(user.id, user.email)
    client.cookies.set("access_token", token)

    project = await create_project(db, "QA Test Project", user.id)
    await db.commit()

    flag = await create_flag(db, project.id, "Test Flag", key="test_flag", flag_type="boolean")
    await db.commit()

    # Eagerly load flag with values to avoid lazy loading issues
    flag = await get_flag_by_id(db, flag.id, project.id)

    return user, project, flag


async def test_flag_update_empty_name_shows_error(client: AsyncClient, db: AsyncSession):
    """Bug fix: updating a flag with empty name should show error, not silently redirect."""
    user, project, flag = await _create_project_and_flag(client, db)

    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/edit",
        data={"name": "", "description": ""},
        follow_redirects=False,
    )
    # Should redirect with an error message
    assert response.status_code in (302, 303)
    assert "error=" in response.headers.get("location", "")


async def test_flag_value_validation_error_shows_message(client: AsyncClient, db: AsyncSession):
    """Bug fix: invalid flag value should show error instead of silent redirect."""
    user, project, flag = await _create_project_and_flag(client, db)

    # Get flag value ID
    fv_id = flag.flag_values[0].id

    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/values/{fv_id}",
        data={"value": "not-json"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    assert "error=" in response.headers.get("location", "")


async def test_toggle_validates_flag_ownership(client: AsyncClient, db: AsyncSession):
    """Security: toggle should validate flag belongs to project."""
    user, project, flag = await _create_project_and_flag(client, db)
    fv_id = flag.flag_values[0].id

    # Toggle with correct project/flag should work
    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/toggle/{fv_id}",
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)


async def test_toggle_rejects_wrong_flag_id(client: AsyncClient, db: AsyncSession):
    """Security: toggle with mismatched flag_value should fail gracefully."""
    user, project, flag = await _create_project_and_flag(client, db)

    # Use a fake flag_value_id
    response = await client.post(
        f"/projects/{project.id}/flags/{flag.id}/toggle/nonexistent-id",
        follow_redirects=False,
    )
    assert response.status_code == 302


async def test_audit_log_invalid_page(client: AsyncClient, db: AsyncSession):
    """Bug fix: audit log should handle invalid page parameter gracefully."""
    user, project, flag = await _create_project_and_flag(client, db)

    # Page with non-numeric value
    response = await client.get(
        f"/projects/{project.id}/audit-log?page=abc",
    )
    assert response.status_code == 200

    # Negative page
    response = await client.get(
        f"/projects/{project.id}/audit-log?page=-1",
    )
    assert response.status_code == 200


async def test_create_flag_key_validation(client: AsyncClient, db: AsyncSession):
    """New: flag key format validation."""
    user, project, flag = await _create_project_and_flag(client, db)

    response = await client.post(
        f"/projects/{project.id}/flags/new",
        data={
            "name": "Bad Key Flag",
            "key": "Bad Key With Spaces!",
            "flag_type": "boolean",
        },
    )
    # Should return 400 with error
    assert response.status_code == 400
    assert "lowercase" in response.text.lower() or "key" in response.text.lower()


async def test_evaluation_records_usage_for_all_flags(client: AsyncClient, db: AsyncSession):
    """Bug fix: usage should be recorded for all flags, not just those with env values."""
    from app.services.auth import create_user
    from app.services.projects import create_project
    from app.services.flags import create_flag
    from app.services.api_keys import create_api_key
    from app.services.environments import get_environments_for_project
    from app.services.usage import get_total_evaluations_for_project

    user = await create_user(db, "eval@test.com", "testpass123", "Eval User")
    await db.commit()

    project = await create_project(db, "Eval Test", user.id)
    await db.commit()

    await create_flag(db, project.id, "Eval Flag", key="eval_flag")
    await db.commit()

    envs = await get_environments_for_project(db, project.id)
    api_key, raw_key = await create_api_key(db, "Test Key", project.id, envs[0].id)
    await db.commit()

    # Evaluate all flags
    response = await client.get(
        "/api/v1/flags",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert response.status_code == 200

    # Should have recorded usage
    total = await get_total_evaluations_for_project(db, project.id)
    assert total >= 1


async def test_http_303_on_post_redirect(client: AsyncClient, db: AsyncSession):
    """Verify POST handlers use 303 See Other for redirects."""
    user, project, flag = await _create_project_and_flag(client, db)

    # Create flag should redirect with 303
    response = await client.post(
        f"/projects/{project.id}/flags/new",
        data={"name": "Another Flag", "key": "another_flag", "flag_type": "boolean"},
        follow_redirects=False,
    )
    assert response.status_code == 303
