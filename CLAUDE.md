# FlagDrop

Phase: DEVELOPMENT

## Project Spec
- **Repo**: https://github.com/arcangelileo/flag-drop
- **Idea**: FlagDrop is a feature flag management platform that lets development teams control feature rollouts without deploying code. Teams create projects, define flags (boolean, string, number, JSON), manage them across environments (dev/staging/production), and evaluate them via a lightweight REST API. A clean dashboard shows flag status, change history, and evaluation analytics. Think LaunchDarkly but simpler, affordable, and self-hostable.
- **Target users**: Software development teams (startups, indie devs, small-to-mid companies) who want feature flags without the enterprise price tag.
- **Revenue model**: Freemium — free tier (1 project, 3 environments, 20 flags, 10k evaluations/month), Pro ($19/mo: 10 projects, unlimited flags, 500k evaluations, audit log), Team ($49/mo: unlimited projects, team members, 5M evaluations, webhooks, SSO).
- **Tech stack**: Python, FastAPI, SQLite (async via aiosqlite), Jinja2 + Tailwind CSS + HTMX, Docker
- **MVP scope**:
  - User authentication (signup, login, JWT httponly cookies)
  - Projects CRUD (each project has its own set of flags)
  - Environments per project (default: development, staging, production)
  - Feature flags CRUD (boolean, string, number, JSON value types)
  - Per-environment flag values and enabled/disabled state
  - API keys per project+environment for server-side evaluation
  - REST API endpoint: `GET /api/v1/flags` (evaluate all flags), `GET /api/v1/flags/{key}` (single flag)
  - Flag change audit log (who changed what, when)
  - Dashboard: project overview, flag list with toggles, evaluation count per flag
  - Usage tracking: count API evaluations per flag per day

## Architecture Decisions
- **Async SQLAlchemy + aiosqlite** for database (SQLite for MVP, PostgreSQL-ready)
- **Alembic** for migrations from the start
- **JWT in httponly cookies** for web auth, **API keys (Bearer token)** for SDK/API auth
- **src layout**: `src/app/` with `api/`, `models/`, `schemas/`, `services/`, `templates/` subdirs
- **Pydantic Settings** for config via environment variables
- **Tailwind CSS via CDN + Inter font** for UI styling
- **HTMX** for interactive dashboard (flag toggles, inline edits)
- **APScheduler** for background jobs (usage aggregation, cleanup)
- **Multi-stage Docker build** with non-root user
- **Tests**: pytest + async httpx test client + in-memory SQLite
- API keys are SHA-256 hashed in the database; only shown once on creation
- Flag evaluation endpoint is optimized: single query, cached per environment, no auth cookie required (API key only)
- Audit log is append-only — records flag changes with actor, timestamp, old/new values

## Task Backlog
- [x] Create project directory and CLAUDE.md with spec and backlog
- [x] Set up pyproject.toml, src layout, and FastAPI app skeleton with health check
- [ ] Database models (User, Project, Environment, Flag, FlagValue, APIKey, AuditLog, UsageRecord)
- [ ] Alembic setup and initial migration
- [ ] Auth system: signup, login, logout, JWT middleware, password hashing
- [ ] Projects CRUD: create, list, update, delete projects
- [ ] Environments management: auto-create defaults, list, add custom environments
- [ ] Flags CRUD: create, list, update, delete flags within a project
- [ ] Flag values: per-environment values and enable/disable toggles
- [ ] API keys: generate, list, revoke per project+environment
- [ ] Flag evaluation API: GET /api/v1/flags and /api/v1/flags/{key} with API key auth
- [ ] Audit log: record all flag changes, display in dashboard
- [ ] Usage tracking: count evaluations, daily aggregation, display stats
- [ ] Dashboard UI: project list, flag management, toggles, audit log, usage charts
- [ ] Write comprehensive tests (models, auth, API, flag evaluation)
- [ ] Dockerfile and docker-compose.yml
- [ ] README with setup, usage, API docs, and deploy instructions

## Progress Log
### Session 1 — IDEATION
- Chose idea: FlagDrop — Feature flag management SaaS
- Created spec, architecture decisions, and task backlog
- Rationale: Feature flags are essential for modern dev teams; LaunchDarkly is expensive ($10+/seat); strong demand for simpler/cheaper alternatives; well-scoped for MVP; API-first design maps well to FastAPI

### Session 2 — SCAFFOLDING
- Created GitHub repo: https://github.com/arcangelileo/flag-drop
- Set up `pyproject.toml` with all dependencies (FastAPI, SQLAlchemy async, aiosqlite, Alembic, JWT, Pydantic Settings, pytest)
- Created `src/app/` layout with `api/`, `models/`, `schemas/`, `services/`, `templates/` subdirs
- Built FastAPI app (`src/app/main.py`) with health check endpoint at `/health`
- Created `config.py` with Pydantic Settings (env-driven, `FLAGDROP_` prefix)
- Created `database.py` with async SQLAlchemy engine and session factory
- Wrote and passed 2 tests (health check + root endpoint) using pytest-asyncio + httpx
- Phase changed from SCAFFOLDING → DEVELOPMENT

## Known Issues
- No virtualenv available (python3-venv not installed, no sudo access). Dependencies installed via `pip3 install --break-system-packages`. Consider Dockerfile for clean env.

## Files Structure
```
flag-drop/
├── CLAUDE.md                  # Project spec, backlog, progress
├── .gitignore                 # Python/IDE/DB ignores
├── pyproject.toml             # Project config, dependencies, tool settings
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py            # FastAPI app entry point
│       ├── config.py          # Pydantic Settings configuration
│       ├── database.py        # Async SQLAlchemy engine & session
│       ├── api/
│       │   ├── __init__.py
│       │   └── health.py      # Health check endpoint
│       ├── models/
│       │   └── __init__.py
│       ├── schemas/
│       │   └── __init__.py
│       ├── services/
│       │   └── __init__.py
│       └── templates/
│           └── layouts/
└── tests/
    ├── __init__.py
    ├── conftest.py            # Test fixtures (async client)
    └── test_health.py         # Health check tests
```
