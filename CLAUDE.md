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
- [x] Database models (User, Project, Environment, Flag, FlagValue, APIKey, AuditLog, UsageRecord)
- [x] Alembic setup and initial migration
- [x] Auth system: signup, login, logout, JWT middleware, password hashing
- [x] Projects CRUD: create, list, update, delete projects
- [x] Environments management: auto-create defaults, list, add custom environments
- [x] Flags CRUD: create, list, update, delete flags within a project
- [x] Flag values: per-environment values and enable/disable toggles
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

### Session 3 — DEVELOPMENT (Models, Alembic, Auth)
- Created all 8 database models: User, Project, Environment, Flag, FlagValue, APIKey, AuditLog, UsageRecord
  - Full relationships, indexes, constraints (unique flag+env, unique flag+env+date)
  - UUID primary keys, timestamps, proper cascade deletes
- Set up Alembic with `render_as_batch=True` for SQLite compatibility
  - Generated and ran initial migration creating all 8 tables
- Built complete auth system:
  - Password hashing with bcrypt via passlib
  - JWT access tokens in httponly cookies (24h expiry)
  - Signup with validation (password match, length, duplicate email)
  - Login with proper error handling
  - Logout (cookie deletion)
  - `/api/auth/me` endpoint for checking auth status
  - `get_current_user` and `get_current_user_optional` dependency injectors
- Created production-quality auth UI:
  - Split-panel login/signup pages with branding panel
  - Tailwind CSS via CDN + Inter font
  - Responsive design (mobile-friendly)
  - Error state rendering with inline feedback
  - Redirect authenticated users away from auth pages
- Created base layout templates (base.html, app.html with nav)
- Created dashboard template with project cards and empty state
- Updated test suite: 40 tests (models, auth services, auth endpoints, health)
- All 40 tests passing with zero warnings

### Session 4 — DEVELOPMENT (Projects, Environments, Flags, Flag Values)
- Built Projects CRUD with full UI:
  - Create project with name/description, auto-generates slug
  - Project settings page with edit form and danger zone (delete)
  - Slug uniqueness per owner, auto-increment on conflict
  - Dashboard shows project cards with flag/env counts
- Built Environments management:
  - Auto-creates 3 defaults (Development/Staging/Production) on project creation
  - List page with color indicators and delete buttons
  - Add custom environments with name and color picker
  - Sort order tracking for consistent display
- Built Flags CRUD with full UI:
  - Create flags with name, auto-generated key (snake_case), type (boolean/string/number/json)
  - Flag list page with type badges, environment status dots, and clickable rows
  - Flag detail page with per-environment toggle switches (HTMX-powered)
  - Edit flag name/description, delete flags
  - Value type validation (JSON parsing + type checking)
- Built Flag Values system:
  - Auto-creates flag values for all environments when flag is created
  - Toggle enabled/disabled per environment with HTMX inline toggle
  - Edit value per environment with save buttons
  - JSON-encoded values validated against flag type
- Created 6 service modules: projects, environments, flags (with tests for slugify, validation)
- Created 6 production-quality templates: project new/settings, environments list, flags list/new/detail
- All templates use Tailwind CSS, responsive design, proper empty/success/error states
- Test suite: 77 tests passing (37 new tests for projects, environments, flags)

## Known Issues
- No virtualenv available (python3-venv not installed, no sudo access). Dependencies installed via `pip3 install --break-system-packages`. Consider Dockerfile for clean env.

## Files Structure
```
flag-drop/
├── CLAUDE.md                  # Project spec, backlog, progress
├── .gitignore                 # Python/IDE/DB ignores
├── pyproject.toml             # Project config, dependencies, tool settings
├── alembic.ini                # Alembic configuration
├── alembic/                   # Database migrations
│   ├── env.py
│   └── versions/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py            # FastAPI app entry point
│       ├── config.py          # Pydantic Settings configuration
│       ├── database.py        # Async SQLAlchemy engine & session
│       ├── api/
│       │   ├── __init__.py
│       │   ├── auth.py        # Auth routes (login, signup, logout)
│       │   ├── dashboard.py   # Dashboard route
│       │   ├── deps.py        # Auth dependency injectors
│       │   ├── environments.py # Environments CRUD routes
│       │   ├── flags.py       # Flags CRUD + toggles routes
│       │   ├── health.py      # Health check endpoint
│       │   └── projects.py    # Projects CRUD routes
│       ├── models/
│       │   ├── __init__.py    # Exports all models
│       │   ├── api_key.py
│       │   ├── audit_log.py
│       │   ├── environment.py
│       │   ├── flag.py
│       │   ├── flag_value.py
│       │   ├── project.py
│       │   ├── usage_record.py
│       │   └── user.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── auth.py        # Auth Pydantic schemas
│       ├── services/
│       │   ├── __init__.py
│       │   ├── auth.py        # Auth service (JWT, passwords, API keys)
│       │   ├── environments.py # Environments service
│       │   ├── flags.py       # Flags + flag values service
│       │   └── projects.py    # Projects service
│       └── templates/
│           ├── layouts/
│           │   ├── app.html   # Authenticated app layout with nav
│           │   └── base.html  # Base HTML with Tailwind/HTMX
│           ├── auth/
│           │   ├── login.html
│           │   └── signup.html
│           ├── dashboard/
│           │   └── index.html
│           ├── environments/
│           │   └── list.html
│           ├── flags/
│           │   ├── detail.html
│           │   ├── list.html
│           │   └── new.html
│           └── projects/
│               ├── new.html
│               └── settings.html
└── tests/
    ├── __init__.py
    ├── conftest.py            # Test fixtures (async client, DB setup)
    ├── test_auth.py           # Auth tests (30 tests)
    ├── test_environments.py   # Environment tests (6 tests)
    ├── test_flags.py          # Flag tests (22 tests)
    ├── test_health.py         # Health check tests (2 tests)
    ├── test_models.py         # Model tests (8 tests)
    └── test_projects.py       # Project tests (11 tests)
```
