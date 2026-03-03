"""Tests for database models."""
import uuid

from sqlalchemy import select

from app.models import APIKey, AuditLog, Environment, Flag, FlagValue, Project, UsageRecord, User


async def test_create_user(db):
    user = User(
        email="user@example.com",
        hashed_password="hashed",
        full_name="Test User",
    )
    db.add(user)
    await db.flush()

    result = await db.execute(select(User).where(User.email == "user@example.com"))
    fetched = result.scalar_one()
    assert fetched.email == "user@example.com"
    assert fetched.full_name == "Test User"
    assert fetched.is_active is True
    assert fetched.id is not None
    assert len(fetched.id) == 36  # UUID format


async def test_create_project(db):
    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="My App", slug="my-app", owner_id=user.id)
    db.add(project)
    await db.flush()

    result = await db.execute(select(Project).where(Project.slug == "my-app"))
    fetched = result.scalar_one()
    assert fetched.name == "My App"
    assert fetched.owner_id == user.id


async def test_create_environment(db):
    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="App", slug="app", owner_id=user.id)
    db.add(project)
    await db.flush()

    env = Environment(name="Production", slug="production", color="#EF4444", project_id=project.id)
    db.add(env)
    await db.flush()

    result = await db.execute(
        select(Environment).where(Environment.project_id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.name == "Production"
    assert fetched.color == "#EF4444"


async def test_create_flag(db):
    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="App", slug="app", owner_id=user.id)
    db.add(project)
    await db.flush()

    flag = Flag(
        key="dark_mode",
        name="Dark Mode",
        description="Enable dark mode",
        flag_type="boolean",
        default_value="false",
        project_id=project.id,
    )
    db.add(flag)
    await db.flush()

    result = await db.execute(select(Flag).where(Flag.key == "dark_mode"))
    fetched = result.scalar_one()
    assert fetched.name == "Dark Mode"
    assert fetched.flag_type == "boolean"
    assert fetched.default_value == "false"


async def test_create_flag_value(db):
    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="App", slug="app", owner_id=user.id)
    db.add(project)
    await db.flush()

    env = Environment(name="Dev", slug="dev", project_id=project.id)
    db.add(env)
    await db.flush()

    flag = Flag(key="feat", name="Feature", project_id=project.id)
    db.add(flag)
    await db.flush()

    fv = FlagValue(flag_id=flag.id, environment_id=env.id, enabled=True, value="true")
    db.add(fv)
    await db.flush()

    result = await db.execute(
        select(FlagValue).where(
            FlagValue.flag_id == flag.id,
            FlagValue.environment_id == env.id,
        )
    )
    fetched = result.scalar_one()
    assert fetched.enabled is True
    assert fetched.value == "true"


async def test_create_api_key(db):
    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="App", slug="app", owner_id=user.id)
    db.add(project)
    await db.flush()

    env = Environment(name="Dev", slug="dev", project_id=project.id)
    db.add(env)
    await db.flush()

    key = APIKey(
        name="Dev Key",
        key_hash="abc123hash",
        key_prefix="fd_abc12345",
        project_id=project.id,
        environment_id=env.id,
    )
    db.add(key)
    await db.flush()

    result = await db.execute(select(APIKey).where(APIKey.key_hash == "abc123hash"))
    fetched = result.scalar_one()
    assert fetched.name == "Dev Key"
    assert fetched.is_active is True


async def test_create_audit_log(db):
    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="App", slug="app", owner_id=user.id)
    db.add(project)
    await db.flush()

    log = AuditLog(
        action="created",
        entity_type="flag",
        entity_id=str(uuid.uuid4()),
        new_value='{"key": "dark_mode"}',
        user_id=user.id,
        project_id=project.id,
    )
    db.add(log)
    await db.flush()

    result = await db.execute(select(AuditLog).where(AuditLog.project_id == project.id))
    fetched = result.scalar_one()
    assert fetched.action == "created"
    assert fetched.entity_type == "flag"


async def test_create_usage_record(db):
    from datetime import date

    user = User(email="u@e.com", hashed_password="h", full_name="U")
    db.add(user)
    await db.flush()

    project = Project(name="App", slug="app", owner_id=user.id)
    db.add(project)
    await db.flush()

    env = Environment(name="Dev", slug="dev", project_id=project.id)
    db.add(env)
    await db.flush()

    flag = Flag(key="feat", name="Feature", project_id=project.id)
    db.add(flag)
    await db.flush()

    record = UsageRecord(
        flag_id=flag.id,
        environment_id=env.id,
        record_date=date.today(),
        evaluation_count=42,
    )
    db.add(record)
    await db.flush()

    result = await db.execute(
        select(UsageRecord).where(UsageRecord.flag_id == flag.id)
    )
    fetched = result.scalar_one()
    assert fetched.evaluation_count == 42
    assert fetched.record_date == date.today()
