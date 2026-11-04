# DARKTRACE Production Deployment Guide

This guide covers deploying the DARKTRACE intelligence platform with the backend hosted on **Render** (free tier, no shell access) and the frontend hosted on **Vercel**.

---

## 1. Environment Variables Overview

> [!IMPORTANT]
> Never commit real secrets or credentials to source control. Configure all values directly in the Render and Vercel dashboards.

### Backend Variables (Render)

| Variable | Required | Description / Example |
| :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | Full PostgreSQL connection URL. Render formats (`postgres://...` or `postgresql://...`) are automatically converted to `postgresql+psycopg://...`. |
| `APP_ENV` | **Yes** | Set to `production`. Enforces strict security checks. |
| `SECRET_KEY` | **Yes** | Cryptographically secure random secret of at least 32 characters. Server **refuses to start** in production if key is weak or uses placeholders. Generate with: `openssl rand -hex 32`. |
| `CORS_ORIGINS` | **Yes** | Comma-separated list of permitted frontend origins. Example: `https://darktrace.vercel.app,https://your-custom-domain.com`. |
| `BOOTSTRAP_ADMIN_EMAIL` | Optional | Email for initial administrator account. |
| `BOOTSTRAP_ADMIN_USERNAME` | Optional | Username for initial administrator account. |
| `BOOTSTRAP_ADMIN_PASSWORD` | Optional | Password for initial administrator account (minimum 10 characters, letters and digits required; distinct from username and email). Plaintext password is never logged. |
| `BOOTSTRAP_ADMIN_FULL_NAME`| Optional | Display name for bootstrapped admin (defaults to `Administrator`). |
| `REPORTS_DIR` | Optional | Storage path for exported dossier reports. Defaults to `backend/reports` (or specify `/tmp/reports`). |
| `PORT` | Auto | Render automatically sets this (defaults to `10000`). |

### Frontend Variables (Vercel)

| Variable | Required | Description / Example |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | **Yes** | URL pointing to the Render backend API, including `/api/v1`. Example: `https://darktrace-backend.onrender.com/api/v1`. |

---

## 2. Deploy Backend on Render

Render's free tier provides Web Services with no interactive shell access. All migrations and administrative bootstrapping are handled automatically via the start command and application lifespan.

### Step 2.1: Provision PostgreSQL on Render
1. In the Render Dashboard, click **New +** → **PostgreSQL**.
2. Set the name (e.g. `darktrace-db`) and select the Free tier.
3. Once provisioned, copy the **Internal Database URL** (if deploying both in the same Render region) or **External Database URL**.

### Step 2.2: Create Backend Web Service
1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your Git repository (`darktrace`).
3. Set the service settings:
   - **Name**: `darktrace-backend`
   - **Region**: Same region as your database
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
     > [!NOTE]
     > Because Render free tier has no shell access, prepending `alembic upgrade head &&` to the start command ensures database migrations are executed automatically on every deploy before the API starts accepting traffic.

### Step 2.3: Add Environment Variables
Under the **Environment** tab, add the following variables:
- `DATABASE_URL`: Paste the database URL from Step 2.1.
- `APP_ENV`: `production`
- `SECRET_KEY`: A random 32+ character string (`openssl rand -hex 32`).
- `CORS_ORIGINS`: `https://<your-vercel-app>.vercel.app` (you can update this once Vercel is set up).
- `BOOTSTRAP_ADMIN_EMAIL`: `admin@darktrace.org`
- `BOOTSTRAP_ADMIN_USERNAME`: `admin`
- `BOOTSTRAP_ADMIN_PASSWORD`: `<YourStrongPassword123!>`

Under **Advanced**:
- **Health Check Path**: `/api/v1/health`

### Step 2.4: Deploy & Verify
1. Click **Create Web Service**.
2. Monitor deploy logs:
   - Alembic runs `alembic upgrade head` and creates all database tables.
   - FastAPI server starts and runs the lifespan startup hook.
   - `bootstrap_admin_user` provisions the administrator account if no admin exists yet.
   - Plaintext passwords are never logged to console or logs.
3. Confirm health check returns HTTP 200:
   ```bash
   curl https://<your-render-backend>.onrender.com/api/v1/health
   ```

---

## 3. Deploy Frontend on Vercel

### Step 3.1: Import Project in Vercel
1. In Vercel Dashboard, click **Add New...** → **Project**.
2. Select your `darktrace` repository.
3. Configure project settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click edit and select `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### Step 3.2: Configure Environment Variables
Add the environment variable:
- `VITE_API_BASE_URL`: `https://<your-render-backend>.onrender.com/api/v1`

### Step 3.3: Deploy
1. Click **Deploy**.
2. Once the build finishes, copy your live Vercel URL (e.g. `https://darktrace.vercel.app`).
3. Return to the Render backend service, update `CORS_ORIGINS` to include your Vercel URL, and trigger a redeploy (or wait for automatic config reload).

---

## 4. Verification & Security Checklist

- [ ] **Health Check**: `GET /api/v1/health` returns `{"success": true, "data": {"status": "ok", "database": "connected"}}`.
- [ ] **Admin Login**: Visit your Vercel frontend, navigate to `/login`, and sign in using the `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD`.
- [ ] **CORS Verification**: Inspect browser console network calls to verify preflight `OPTIONS` and standard requests succeed without CORS errors.
- [ ] **Clean Up Bootstrap Secrets (Recommended)**: Once your administrator account is confirmed active, you may safely remove `BOOTSTRAP_ADMIN_PASSWORD` from Render environment variables. Future restarts detect the existing admin and skip bootstrap automatically.
