"""Tests for authentication system."""
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_api_key,
    hash_password,
    verify_password,
    generate_api_key,
)


# --- Password hashing tests ---


def test_hash_password():
    hashed = hash_password("mypassword")
    assert hashed != "mypassword"
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


# --- JWT tests ---


def test_create_and_decode_token():
    token = create_access_token("user-123", "user@example.com")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "access"


def test_decode_invalid_token():
    payload = decode_access_token("invalid-token-string")
    assert payload is None


def test_decode_tampered_token():
    token = create_access_token("user-123", "user@example.com")
    # Tamper with the token
    tampered = token[:-5] + "XXXXX"
    payload = decode_access_token(tampered)
    assert payload is None


# --- API key tests ---


def test_generate_api_key():
    raw_key, key_hash, key_prefix = generate_api_key()
    assert raw_key.startswith("fd_")
    assert len(key_hash) == 64  # SHA-256 hex digest
    assert len(key_prefix) == 12
    assert key_prefix == raw_key[:12]


def test_hash_api_key():
    raw_key, expected_hash, _ = generate_api_key()
    assert hash_api_key(raw_key) == expected_hash


# --- Auth service integration tests ---


async def test_create_user_service(db):
    from app.services.auth import create_user, get_user_by_email

    user = await create_user(db, "new@example.com", "password123", "New User")
    assert user.email == "new@example.com"
    assert user.full_name == "New User"
    assert user.hashed_password != "password123"

    fetched = await get_user_by_email(db, "new@example.com")
    assert fetched is not None
    assert fetched.id == user.id


async def test_authenticate_user_success(db):
    from app.services.auth import authenticate_user, create_user

    await create_user(db, "auth@example.com", "correctpass", "Auth User")
    await db.flush()

    result = await authenticate_user(db, "auth@example.com", "correctpass")
    assert result is not None
    assert result.email == "auth@example.com"


async def test_authenticate_user_wrong_password(db):
    from app.services.auth import authenticate_user, create_user

    await create_user(db, "auth@example.com", "correctpass", "Auth User")
    await db.flush()

    result = await authenticate_user(db, "auth@example.com", "wrongpass")
    assert result is None


async def test_authenticate_user_nonexistent(db):
    from app.services.auth import authenticate_user

    result = await authenticate_user(db, "nobody@example.com", "anypass")
    assert result is None


# --- Auth endpoint tests ---


async def test_signup_page(client):
    response = await client.get("/signup")
    assert response.status_code == 200
    assert "Create your account" in response.text


async def test_login_page(client):
    response = await client.get("/login")
    assert response.status_code == 200
    assert "Welcome back" in response.text


async def test_signup_success(client):
    response = await client.post("/signup", data={
        "email": "newuser@example.com",
        "password": "strongpass123",
        "confirm_password": "strongpass123",
        "full_name": "New User",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/dashboard"
    assert "access_token" in response.cookies


async def test_signup_password_mismatch(client):
    response = await client.post("/signup", data={
        "email": "newuser@example.com",
        "password": "strongpass123",
        "confirm_password": "different123",
        "full_name": "New User",
    })
    assert response.status_code == 400
    assert "Passwords do not match" in response.text


async def test_signup_short_password(client):
    response = await client.post("/signup", data={
        "email": "newuser@example.com",
        "password": "short",
        "confirm_password": "short",
        "full_name": "New User",
    })
    assert response.status_code == 400
    assert "at least 8 characters" in response.text


async def test_signup_missing_name(client):
    response = await client.post("/signup", data={
        "email": "newuser@example.com",
        "password": "strongpass123",
        "confirm_password": "strongpass123",
        "full_name": "",
    })
    assert response.status_code == 400
    assert "Full name is required" in response.text


async def test_signup_duplicate_email(client):
    # First signup
    await client.post("/signup", data={
        "email": "dup@example.com",
        "password": "strongpass123",
        "confirm_password": "strongpass123",
        "full_name": "First User",
    }, follow_redirects=False)

    # Clear cookies
    client.cookies.clear()

    # Second signup with same email
    response = await client.post("/signup", data={
        "email": "dup@example.com",
        "password": "strongpass123",
        "confirm_password": "strongpass123",
        "full_name": "Second User",
    })
    assert response.status_code == 409
    assert "already exists" in response.text


async def test_login_success(client):
    # First create a user via signup
    await client.post("/signup", data={
        "email": "login@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123",
        "full_name": "Login User",
    }, follow_redirects=False)

    client.cookies.clear()

    # Now login
    response = await client.post("/login", data={
        "email": "login@example.com",
        "password": "testpass123",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/dashboard"
    assert "access_token" in response.cookies


async def test_login_wrong_password(client):
    # Create user
    await client.post("/signup", data={
        "email": "login@example.com",
        "password": "testpass123",
        "confirm_password": "testpass123",
        "full_name": "Login User",
    }, follow_redirects=False)

    client.cookies.clear()

    response = await client.post("/login", data={
        "email": "login@example.com",
        "password": "wrongpass",
    })
    assert response.status_code == 401
    assert "Invalid email or password" in response.text


async def test_login_empty_fields(client):
    response = await client.post("/login", data={
        "email": "",
        "password": "",
    })
    assert response.status_code == 400
    assert "required" in response.text


async def test_logout(client):
    response = await client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_dashboard_requires_auth(client):
    response = await client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_dashboard_with_auth(authenticated_client):
    client, user = authenticated_client
    response = await client.get("/dashboard")
    assert response.status_code == 200
    assert "Welcome back" in response.text
    assert user.full_name.split(" ")[0] in response.text


async def test_me_endpoint_authenticated(authenticated_client):
    client, user = authenticated_client
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user.email
    assert data["full_name"] == user.full_name


async def test_me_endpoint_unauthenticated(client):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_login_page_redirects_when_authenticated(authenticated_client):
    client, _ = authenticated_client
    response = await client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


async def test_signup_page_redirects_when_authenticated(authenticated_client):
    client, _ = authenticated_client
    response = await client.get("/signup", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


async def test_root_redirects_to_login(client):
    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
