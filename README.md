# FlagDrop

**Simple, self-hostable feature flag management for development teams.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-148%20passing-brightgreen.svg)](#testing)

FlagDrop lets development teams control feature rollouts without deploying code. Create projects, define flags (boolean, string, number, JSON), manage them across environments, and evaluate them via a lightweight REST API. A clean dashboard shows flag status, change history, and evaluation analytics.

Think **LaunchDarkly** -- but simpler, affordable, and self-hostable.

---

## Features

- **User Authentication** -- Signup, login, logout with JWT tokens in httponly cookies
- **Projects** -- Organize flags by project, each with its own settings and API keys
- **Environments** -- Per-project environments (development, staging, production) with custom environments support
- **Feature Flags** -- Boolean, string, number, and JSON value types with validation
- **Per-Environment Values** -- Toggle flags on/off and set different values per environment
- **REST API** -- Evaluate flags via `GET /api/v1/flags` and `GET /api/v1/flags/{key}`
- **API Key Management** -- SHA-256 hashed keys with `fd_` prefix, shown once on creation
- **Audit Log** -- Append-only log of who changed what, when, with old/new value diffs
- **Usage Analytics** -- Evaluation counts per flag per day with charts and rankings
- **Dashboard** -- Tailwind CSS interface with HTMX-powered interactive toggles
- **Self-Hostable** -- Run on your own infrastructure with Docker, SQLite or PostgreSQL

---

## Quick Start

### Docker (recommended)

```bash
# One-liner: generate a secret key and start FlagDrop
FLAGDROP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))") \
  docker compose up -d
```

Open [http://localhost:8000](http://localhost:8000), create an account, and start managing feature flags.

To stop:

```bash
docker compose down
```

### Local Development

```bash
# Clone the repository
git clone https://github.com/arcangelileo/flag-drop.git
cd flag-drop

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy and edit environment config
cp .env.example .env
# Edit .env and set FLAGDROP_SECRET_KEY to a random string

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Configuration

FlagDrop is configured through environment variables with the `FLAGDROP_` prefix. You can also use a `.env` file in the project root (see `.env.example`).

| Variable | Description | Default | Required |
|---|---|---|---|
| `FLAGDROP_SECRET_KEY` | JWT signing key | `change-me-...` | **Yes** |
| `FLAGDROP_DATABASE_URL` | Async database URL | `sqlite+aiosqlite:///./flagdrop.db` | No |
| `FLAGDROP_HOST` | Server bind address | `0.0.0.0` | No |
| `FLAGDROP_PORT` | Server port | `8000` | No |
| `FLAGDROP_DEBUG` | Enable debug mode | `false` | No |
| `FLAGDROP_ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiry (minutes) | `1440` (24h) | No |
| `FLAGDROP_JWT_ALGORITHM` | JWT signing algorithm | `HS256` | No |

> **Important:** Always set a strong, unique `FLAGDROP_SECRET_KEY` in production. Generate one with:
> ```bash
> python3 -c "import secrets; print(secrets.token_urlsafe(64))"
> ```

---

## API Documentation

FlagDrop provides a REST API for evaluating feature flags from your application code. Authenticate using an API key generated from the dashboard.

### Authentication

All evaluation API requests require a Bearer token:

```
Authorization: Bearer fd_your_api_key
```

API keys are scoped to a specific project and environment. Generate them from the **API Keys** page in the dashboard.

### Evaluate All Flags

```
GET /api/v1/flags
```

Returns all flags for the project and environment associated with the API key.

```bash
curl -s -H "Authorization: Bearer fd_your_api_key" \
  http://localhost:8000/api/v1/flags | python3 -m json.tool
```

**Response:**

```json
{
  "flags": {
    "dark_mode": {
      "key": "dark_mode",
      "enabled": true,
      "value": true,
      "type": "boolean"
    },
    "welcome_message": {
      "key": "welcome_message",
      "enabled": true,
      "value": "Hello, beta users!",
      "type": "string"
    },
    "max_upload_size": {
      "key": "max_upload_size",
      "enabled": false,
      "value": 50,
      "type": "number"
    }
  },
  "environment": "production",
  "project": "my-app"
}
```

### Evaluate Single Flag

```
GET /api/v1/flags/{key}
```

Returns a single flag by its key.

```bash
curl -s -H "Authorization: Bearer fd_your_api_key" \
  http://localhost:8000/api/v1/flags/dark_mode
```

**Response:**

```json
{
  "key": "dark_mode",
  "enabled": true,
  "value": true,
  "type": "boolean"
}
```

### Integration Example

```python
import requests

API_KEY = "fd_your_api_key"
BASE_URL = "http://localhost:8000"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Evaluate all flags
response = requests.get(f"{BASE_URL}/api/v1/flags", headers=headers)
flags = response.json()["flags"]

if flags["dark_mode"]["enabled"] and flags["dark_mode"]["value"]:
    enable_dark_mode()

# Evaluate a single flag
response = requests.get(f"{BASE_URL}/api/v1/flags/max_upload_size", headers=headers)
flag = response.json()
max_size = flag["value"] if flag["enabled"] else 10  # fallback
```

### Error Responses

| Status Code | Description |
|---|---|
| `401 Unauthorized` | Missing, invalid, or revoked API key |
| `404 Not Found` | Flag key does not exist |

### All Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Health check |
| `GET` | `/api/v1/flags` | API Key | Evaluate all flags |
| `GET` | `/api/v1/flags/{key}` | API Key | Evaluate single flag |
| `POST` | `/api/auth/signup` | None | Create account |
| `POST` | `/api/auth/login` | None | Login |
| `POST` | `/api/auth/logout` | Cookie | Logout |
| `GET` | `/api/auth/me` | Cookie | Current user info |

Interactive API docs: [/docs](http://localhost:8000/docs) (Swagger UI) | [/redoc](http://localhost:8000/redoc) (ReDoc)

---

## Architecture

```
                    +------------------+
                    |   Browser/HTMX   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  FastAPI Router   |
                    |  (Jinja2 + API)  |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Service Layer    |
                    |  (Business Logic) |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  SQLAlchemy ORM   |
                    |  (Async Sessions) |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  SQLite/PostgreSQL |
                    +-------------------+
```

### Key Design Decisions

- **Async-first**: All database operations use async SQLAlchemy with `aiosqlite`, making it easy to swap to PostgreSQL (`asyncpg`) for production.
- **Service layer**: Business logic is separated from route handlers into `services/` modules for testability.
- **JWT in httponly cookies**: Web authentication uses secure, httponly cookies -- not localStorage -- to prevent XSS token theft.
- **API keys are hashed**: SHA-256 hashed in the database. The raw key is shown exactly once on creation.
- **Audit log is append-only**: Every flag mutation is recorded with actor, timestamp, and old/new values.
- **Alembic migrations from day one**: Database schema changes are versioned and reproducible.

### Project Structure

```
flag-drop/
├── src/
│   └── app/
│       ├── main.py            # FastAPI application entry point
│       ├── config.py          # Pydantic Settings (env vars)
│       ├── database.py        # Async SQLAlchemy engine + session
│       ├── api/               # Route handlers
│       │   ├── auth.py        #   Authentication
│       │   ├── dashboard.py   #   Dashboard + usage analytics
│       │   ├── projects.py    #   Projects CRUD
│       │   ├── environments.py#   Environments management
│       │   ├── flags.py       #   Flags CRUD + toggles
│       │   ├── api_keys.py    #   API key management
│       │   ├── evaluation.py  #   Flag evaluation REST API
│       │   ├── audit.py       #   Audit log views
│       │   ├── deps.py        #   Auth dependency injectors
│       │   └── health.py      #   Health check
│       ├── models/            # SQLAlchemy models (8 tables)
│       ├── schemas/           # Pydantic request/response schemas
│       ├── services/          # Business logic layer
│       └── templates/         # Jinja2 + Tailwind CSS templates
├── tests/                     # pytest test suite (148 tests)
├── alembic/                   # Database migrations
├── Dockerfile                 # Multi-stage production build
├── docker-compose.yml         # Docker Compose deployment
├── .env.example               # Environment variable reference
├── alembic.ini                # Alembic configuration
└── pyproject.toml             # Project dependencies + tool config
```

### Database Models

| Model | Description |
|---|---|
| `User` | Accounts with hashed passwords |
| `Project` | Feature flag projects (owned by users) |
| `Environment` | Per-project environments (dev, staging, prod) |
| `Flag` | Feature flags with key, name, type |
| `FlagValue` | Per-environment flag values and enabled state |
| `APIKey` | SHA-256 hashed API keys per project+environment |
| `AuditLog` | Append-only change log with diffs |
| `UsageRecord` | Daily evaluation counts per flag+environment |

---

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_evaluation.py
```

The test suite includes **148 tests** covering:

| Test File | Tests | Coverage |
|---|---|---|
| `test_auth.py` | 30 | Signup, login, logout, JWT, password hashing |
| `test_flags.py` | 22 | Flag CRUD, toggles, value types, validation |
| `test_projects.py` | 11 | Project CRUD, slugs, ownership |
| `test_evaluation.py` | 10 | Flag evaluation API, auth, response format |
| `test_evaluation_advanced.py` | 11 | Type-specific eval, multi-env, edge cases |
| `test_dashboard.py` | 10 | Dashboard stats, usage page, charts |
| `test_models.py` | 8 | SQLAlchemy model creation and relationships |
| `test_usage.py` | 8 | Usage recording, incrementing, daily stats |
| `test_qa.py` | 8 | Security fixes, validation, HTTP correctness |
| `test_integration.py` | 7 | End-to-end workflows, cascade delete |
| `test_environments.py` | 6 | Environment CRUD, defaults, custom envs |
| `test_health.py` | 2 | Health check endpoint |

Tests use an in-memory SQLite database and async httpx test client -- no external services needed.

### Linting

```bash
ruff check src/ tests/
```

---

## Docker Deployment

### Build and Run

```bash
# Set your secret key
export FLAGDROP_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# Start with Docker Compose
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### Production Checklist

1. Set a strong `FLAGDROP_SECRET_KEY` (never use the default)
2. Use a named volume for data persistence (`flagdrop-data`)
3. Place behind a reverse proxy (nginx, Caddy, Traefik) for HTTPS
4. Consider PostgreSQL for multi-instance deployments
5. Set `FLAGDROP_DEBUG=false` (default)

### Custom Port

```bash
FLAGDROP_SECRET_KEY=your-key FLAGDROP_PORT=3000 docker compose up -d
```

### Database Migrations

Migrations run automatically on container startup via `alembic upgrade head`.

To run manually:

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com) |
| **ORM** | [SQLAlchemy 2.0](https://www.sqlalchemy.org) (async) |
| **Database** | [SQLite](https://sqlite.org) via [aiosqlite](https://github.com/omnilib/aiosqlite) (PostgreSQL-ready) |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org) |
| **Auth** | JWT ([python-jose](https://github.com/mpdavis/python-jose)) + bcrypt ([passlib](https://passlib.readthedocs.io)) |
| **Templates** | [Jinja2](https://jinja.palletsprojects.com) |
| **CSS** | [Tailwind CSS](https://tailwindcss.com) (CDN) + Inter font |
| **Interactivity** | [HTMX](https://htmx.org) |
| **Testing** | [pytest](https://pytest.org) + [httpx](https://www.python-httpx.org) (async) |
| **Config** | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| **Container** | Docker with multi-stage build, tini init |

---

## Plans and Pricing

| | **Free** | **Pro** | **Team** |
|---|---|---|---|
| **Price** | $0/mo | $19/mo | $49/mo |
| **Projects** | 1 | 10 | Unlimited |
| **Environments** | 3 | Unlimited | Unlimited |
| **Flags** | 20 | Unlimited | Unlimited |
| **Evaluations** | 10k/mo | 500k/mo | 5M/mo |
| **Audit Log** | -- | Yes | Yes |
| **Team Members** | 1 | 1 | Unlimited |
| **Webhooks** | -- | -- | Yes |
| **SSO** | -- | -- | Yes |

---

## Roadmap

- [x] User authentication (signup, login, JWT)
- [x] Projects and environments CRUD
- [x] Feature flags with per-environment values
- [x] REST API for flag evaluation
- [x] API key management (SHA-256 hashed)
- [x] Audit log with change diffs
- [x] Usage analytics with charts
- [x] Dashboard with HTMX interactive toggles
- [x] Docker deployment with multi-stage build
- [ ] Webhooks for flag change notifications
- [ ] Team collaboration and role-based access
- [ ] SSO integration (SAML, OIDC)
- [ ] PostgreSQL production deployment guide
- [ ] SDK libraries (Python, JavaScript, Go)
- [ ] Percentage-based rollouts and user targeting
- [ ] Flag scheduling (auto-enable/disable at a date)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Run the linter: `ruff check src/ tests/`
6. Commit your changes: `git commit -m "Add my feature"`
7. Push and open a pull request

Please ensure all tests pass and follow the existing code style.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
