# FlagDrop

**Simple, self-hostable feature flag management for development teams.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

FlagDrop lets development teams control feature rollouts without deploying code. Create projects, define flags (boolean, string, number, JSON), manage them across environments, and evaluate them via a lightweight REST API. A clean dashboard shows flag status, change history, and evaluation analytics.

Think **LaunchDarkly** -- but simpler, affordable, and self-hostable.

---

## Features

- **User Authentication** -- Signup, login, logout with JWT tokens in httponly cookies
- **Projects** -- Organize flags by project, each with its own settings and API keys
- **Environments** -- Per-project environments (development, staging, production) with custom environments support
- **Feature Flags** -- Boolean, string, number, and JSON value types
- **Per-Environment Values** -- Toggle flags on/off and set different values per environment
- **REST API** -- Evaluate flags via `GET /api/v1/flags` and `GET /api/v1/flags/{key}`
- **API Key Management** -- SHA-256 hashed keys with `fd_` prefix, shown once on creation
- **Audit Log** -- Append-only log of who changed what, when, with old/new value diffs
- **Usage Analytics** -- Evaluation counts per flag per day
- **Dashboard** -- Tailwind CSS interface with HTMX-powered interactive toggles
- **Self-Hostable** -- Run on your own infrastructure with SQLite or PostgreSQL

---

## Quick Start

### Prerequisites

- Python 3.11 or higher

### Installation

```bash
# Clone the repository
git clone https://github.com/arcangelileo/flag-drop.git
cd flag-drop

# Install dependencies
pip install -e .

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser, create an account, and start managing your feature flags.

---

## Docker Setup

```bash
docker compose up -d
```

The application will be available at [http://localhost:8000](http://localhost:8000).

To stop the application:

```bash
docker compose down
```

---

## Configuration

FlagDrop is configured through environment variables with the `FLAGDROP_` prefix. You can also use a `.env` file in the project root.

| Variable | Description | Default |
|---|---|---|
| `FLAGDROP_DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./flagdrop.db` |
| `FLAGDROP_SECRET_KEY` | JWT signing key (**change in production**) | `change-me-in-production-use-a-real-secret-key` |
| `FLAGDROP_HOST` | Server bind address | `0.0.0.0` |
| `FLAGDROP_PORT` | Server port | `8000` |
| `FLAGDROP_DEBUG` | Enable debug mode | `false` |

**Example `.env` file:**

```env
FLAGDROP_SECRET_KEY=your-secure-random-secret-key-here
FLAGDROP_DATABASE_URL=sqlite+aiosqlite:///./flagdrop.db
FLAGDROP_DEBUG=false
```

> **Important:** Always set a strong, unique `FLAGDROP_SECRET_KEY` in production. The default value is not secure.

---

## API Documentation

FlagDrop provides a REST API for evaluating feature flags from your application code. Authenticate using an API key generated from the dashboard.

### Authentication

All API requests require a Bearer token in the `Authorization` header:

```
Authorization: Bearer fd_your_api_key
```

API keys are scoped to a specific project and environment. Generate them from the **API Keys** page in the dashboard.

### Endpoints

#### Evaluate All Flags

```
GET /api/v1/flags
```

Returns all flags for the project and environment associated with the API key.

```bash
curl -H "Authorization: Bearer fd_your_api_key" \
  http://localhost:8000/api/v1/flags
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

#### Evaluate Single Flag

```
GET /api/v1/flags/{key}
```

Returns a single flag by its key.

```bash
curl -H "Authorization: Bearer fd_your_api_key" \
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

#### Error Responses

| Status Code | Description |
|---|---|
| `401 Unauthorized` | Missing, invalid, or revoked API key |
| `404 Not Found` | Flag key does not exist |

### Additional Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/auth/signup` | Create account |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/logout` | Logout |
| `GET` | `/api/auth/me` | Current user info |

Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI) and [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc).

---

## Project Structure

```
flag-drop/
├── alembic/                   # Database migrations
├── src/
│   └── app/
│       ├── main.py            # FastAPI application entry point
│       ├── config.py          # Settings (env vars with FLAGDROP_ prefix)
│       ├── database.py        # Async SQLAlchemy engine and session
│       ├── api/               # Route handlers
│       │   ├── auth.py        #   Authentication (signup, login, logout)
│       │   ├── dashboard.py   #   Dashboard views
│       │   ├── projects.py    #   Projects CRUD
│       │   ├── environments.py#   Environments management
│       │   ├── flags.py       #   Flags CRUD and toggles
│       │   ├── api_keys.py    #   API key management
│       │   ├── evaluation.py  #   Flag evaluation REST API
│       │   ├── audit.py       #   Audit log views
│       │   └── health.py      #   Health check
│       ├── models/            # SQLAlchemy models (8 tables)
│       ├── schemas/           # Pydantic request/response schemas
│       ├── services/          # Business logic layer
│       └── templates/         # Jinja2 + Tailwind CSS templates
├── tests/                     # pytest test suite (105 tests)
├── alembic.ini
└── pyproject.toml
```

---

## Development

### Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

Tests use an in-memory SQLite database and async httpx test client. The suite includes 105 tests covering models, authentication, projects, environments, flags, API keys, flag evaluation, and audit logging.

### Linting

```bash
ruff check src/ tests/
```

### Database Migrations

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
| **Auth** | JWT (python-jose) + bcrypt (passlib) |
| **Templates** | [Jinja2](https://jinja.palletsprojects.com) |
| **CSS** | [Tailwind CSS](https://tailwindcss.com) (CDN) + Inter font |
| **Interactivity** | [HTMX](https://htmx.org) |
| **Testing** | [pytest](https://pytest.org) + [httpx](https://www.python-httpx.org) (async) |
| **Config** | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |

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

- [ ] Dashboard UI polish: charts, usage graphs, flag search
- [ ] Comprehensive test coverage expansion
- [ ] Dockerfile and docker-compose.yml
- [ ] Webhooks for flag change notifications
- [ ] Team collaboration and role-based access
- [ ] SSO integration (SAML, OIDC)
- [ ] PostgreSQL production deployment guide
- [ ] SDK libraries (Python, JavaScript, Go)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
