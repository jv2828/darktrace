# DARKTRACE (Phase 1: Project Skeleton)

DARKTRACE is a dark web threat-intelligence and actor-correlation platform developed for an academic cybersecurity project. 

Phase 1 provides the verified architectural foundation:
- Containerized PostgreSQL 16 database configuration.
- FastAPI backend with a unified JSON response envelope, configuration loading, and database health check.
- Modern React frontend (Vite + Tailwind CSS v4) with real-time system status verification.
- Pytest test suite validating API health and failure states.

---

## Prerequisites

Ensure the following tools are installed on your workstation:
- **Python 3.11+**
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

#### Run Pytest Test Suite
```bash
pytest -v
```

#### Start FastAPI Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000/api/v1`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`

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
  │   └── api-conventions.md     # Unified response envelope specifications
  ├── backend/
  │   ├── requirements.txt       # Pinned backend dependencies
  │   ├── pytest.ini             # Pytest configuration
  │   ├── app/
  │   │   ├── main.py            # FastAPI initialization & global exception handlers
  │   │   ├── core/
  │   │   │   ├── config.py      # Settings class loading .env via Pydantic
  │   │   │   └── responses.py   # Envelope helpers: success() and error()
  │   │   ├── db/
  │   │   │   └── session.py     # SQLAlchemy 2.0 engine & get_db dependency
  │   │   ├── api/
  │   │   │   └── v1/
  │   │   │       ├── health.py  # GET /api/v1/health executing SELECT 1
  │   │   │       └── router.py  # V1 router aggregation
  │   │   ├── services/          # Business logic (Phase 2+)
  │   │   └── analysis/          # Threat correlation algorithms (Phase 2+)
  │   └── tests/
  │       └── test_health.py     # Tests for health status and error envelope
  └── frontend/                  # React + Vite + Tailwind CSS application
      ├── src/
      │   ├── App.jsx            # Dark-themed System Status view
      │   ├── lib/api.js         # Fetch client with envelope parser
      │   └── index.css          # Tailwind CSS v4 styling
      ├── .env.example           # Frontend API base URL template
      ├── package.json           # Node scripts and dependencies
      └── vite.config.js         # Vite configuration with Tailwind plugin
```

