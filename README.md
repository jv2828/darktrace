# DARKTRACE

DARKTRACE is a dark web threat-intelligence and actor-correlation platform developed for an academic cybersecurity project. 

### Implementation Phases:
- **Phase 1: Project Skeleton**: Containerized PostgreSQL 16 database, FastAPI backend with a unified JSON response envelope, configuration loading, health checks, React (Vite + Tailwind CSS v4) status interface, and test harness.
- **Phase 2: Database Layer**: Complete 17-table relational schema with SQLAlchemy 2.0 ORM, PostgreSQL native ENUMs, partial indexes, check constraints, cascade semantics, Alembic migrations, and automated schema round-trip testing on an isolated test database.
- **Phase 3: Authentication & Role Management (Current)**: Argon2id password hashing, JWT bearer tokens (HS256), stateless token validation with immediate deactivation revoking, 5-strike account lockout protection, anti-enumeration security, self-protection guards, role-based access control (Admin vs. Investigator), and administrative user management.

---

## Prerequisites

Ensure the following tools are installed on your workstation:
- **Python 3.11+** (Python 3.12 recommended)
- **Node.js 20+** (includes `npm`)
- **Docker Desktop** (with Docker Compose support)

---

## Quickstart Guide

### 1. Clone & Environment Configuration

Copy the example environment configuration into the root `.env` file:

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

The default credentials inside `.env` configure:
- `DB_NAME=darktrace`
- `DB_USER=darktrace`
- `DB_PASSWORD=change_me`
- `DB_HOST=localhost`
- `DB_PORT=5432`
- `TEST_DB_NAME=darktrace_test`
- `SECRET_KEY=change_me_later`
- `CORS_ORIGINS=http://localhost:5173`

---

### 2. Start PostgreSQL via Docker Compose

Launch the PostgreSQL 16 container in the background:

**macOS / Linux / Windows:**
```bash
docker compose up -d
```

To verify the container is healthy:
```bash
docker compose ps
```

To stop the PostgreSQL container:
```bash
docker compose down
```

---

### 3. Backend Setup & Run

Open a terminal and navigate to the `backend/` directory.

#### Create and Activate Virtual Environment

**macOS / Linux:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Apply Database Migrations (Alembic)
With PostgreSQL running, apply the database schema:
```bash
alembic upgrade head
```

Additional useful Alembic migration commands:
```bash
# Roll back one migration
alembic downgrade -1

# Roll back all migrations to base schema
alembic downgrade base

# Autogenerate a new migration from ORM model changes
alembic revision --autogenerate -m "migration_description"
```

#### Bootstrap First Administrator Account
To create your first administrative user interactively:
```bash
python -m app.scripts.create_admin
```

#### Run Pytest Test Suite
```bash
pytest -v
```
*(All 40+ tests execute against an isolated test database `darktrace_test` defined by `TEST_DB_NAME` and will never touch the primary `darktrace` database).*

#### Start FastAPI Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000/api/v1`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`
- Auth Endpoints: `http://localhost:8000/api/v1/auth/login`, `http://localhost:8000/api/v1/auth/me`
- User Admin Endpoints: `http://localhost:8000/api/v1/users`

---

### 4. Frontend Setup & Run

In a separate terminal, navigate to the `frontend/` directory.

#### Install Dependencies
```bash
cd frontend
npm install
```

#### Configure Environment
Copy the frontend environment example:

**macOS / Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

#### Start Vite Development Server
```bash
npm run dev
```
Open your browser to: `http://localhost:5173`

---

## Repository Structure

```
darktrace/
  ├── README.md                  # Project overview and run guide
  ├── .gitignore                 # Ignore patterns for secrets, Python, Node
  ├── .env.example               # Root environment variable template
  ├── docker-compose.yml         # PostgreSQL 16 service definition
  ├── docs/
  │   ├── architecture.md        # Architecture overview & ethical guidelines
  │   ├── api-conventions.md     # Unified response envelope specifications
  │   ├── database.md            # 17-table schema, indexing, and cascade rules
  │   └── auth.md                # RBAC matrix, JWT tokens, lockout & security
  ├── backend/
  │   ├── requirements.txt       # Pinned backend dependencies
  │   ├── pytest.ini             # Pytest configuration
  │   ├── alembic.ini            # Alembic configuration
  │   ├── alembic/               # Database migration scripts
  │   ├── app/
  │   │   ├── main.py            # FastAPI initialization & global exception handlers
  │   │   ├── core/
  │   │   │   ├── config.py      # Settings class loading .env via Pydantic
  │   │   │   ├── exceptions.py  # Structured APIException class
  │   │   │   ├── responses.py   # Envelope helpers: success() and error()
  │   │   │   └── security.py    # Argon2id hashing, JWT encode/decode, policies
  │   │   ├── db/
  │   │   │   ├── base.py        # Declarative Base & TimestampMixin
  │   │   │   └── session.py     # SQLAlchemy 2.0 engine & get_db dependency
  │   │   ├── models/            # 17 SQLAlchemy ORM model entities
  │   │   ├── schemas/           # Pydantic validation models (Auth, User)
  │   │   ├── api/
  │   │   │   ├── deps.py        # Auth dependencies (get_current_user, require_role)
  │   │   │   └── v1/
  │   │   │       ├── health.py  # GET /api/v1/health executing SELECT 1
  │   │   │       ├── system.py  # GET /api/v1/system/info (Admin-only diagnostics)
  │   │   │       ├── auth.py    # Login, session me, change password
  │   │   │       ├── users.py   # User creation, listing, updates, reset password
  │   │   │       └── router.py  # V1 router aggregation
  │   │   ├── scripts/
  │   │   │   └── create_admin.py # CLI administrator provisioning script
  │   │   ├── services/          # Business logic
  │   │   └── analysis/          # Threat correlation algorithms
  │   └── tests/
  │       ├── conftest.py        # Isolated test DB fixtures & rollback sessions
  │       ├── test_health.py     # Tests for health status and error envelope
  │       ├── test_schema.py     # 11 tests verifying schema constraints & cascades
  │       └── test_auth.py       # 26 tests for JWT, Argon2, lockout, and RBAC
  └── frontend/                  # React + Vite + Tailwind CSS application
      ├── src/
      │   ├── App.jsx            # Dark-themed System Status view
      │   ├── lib/api.js         # Fetch client with envelope parser
      │   └── index.css          # Tailwind CSS v4 styling
      ├── .env.example           # Frontend API base URL template
      ├── package.json           # Node scripts and dependencies
      └── vite.config.js         # Vite configuration with Tailwind plugin
```

