# Business Analytics Platform

Simple business analytics platform with a FastAPI backend and a React/Vite frontend.

This document covers **manual deployment** to Azure App Service. There is no CI/CD pipeline for this — deployment is a deliberate, manual step you run from your own machine.

## Prerequisites

- Azure subscription with Contributor access to the target resource group
- Azure CLI (`az`) installed and logged in (`az login`)
- Python 3.12.x and Node.js 22 LTS / npm 10.x installed locally (needed to build before packaging)
- An Azure Database for PostgreSQL (Flexible Server) instance already provisioned, with a database created for this app

## Required Azure resources

- Resource Group (e.g. `AI26s-Team-B`)
- App Service Plan (Linux, Python 3.12 runtime)
- App Service / Web App (e.g. `app-ai26s-teamb-api-dev`)
- Azure Database for PostgreSQL Flexible Server

Adjust names/region to match your environment.

## Required application settings / environment variables

Set these under App Service → Configuration → Application settings (or via `az webapp config appsettings set`):

- `JWT_SECRET_KEY` — secret used to sign JWTs
- `DB_HOST` — Postgres server hostname
- `DB_PORT` — Postgres port (defaults to `5432` if unset)
- `DB_NAME` — database name
- `DB_USER` — database user
- `DB_PASSWORD` — database password

For local development, copy `backend/.env.example` to `backend/.env` and fill these in — the backend loads them via `python-dotenv`.

## Backend deployment steps

1. Build the frontend first (see "Frontend build" below) and copy the output into `backend/static/`.
2. From the repo root, generate the deployment zip:
   ```bash
   python make-deploy-zip.py
   ```
   Always use this script rather than PowerShell's `Compress-Archive` — `Compress-Archive` writes path separators that break on Linux (`ModuleNotFoundError: No module named 'app'`).
3. Deploy the zip:
   ```bash
   az webapp deployment source config-zip \
     -n <app-service-name> -g <resource-group> --src backend-deploy.zip
   ```
4. Set the App Service Startup Command to run gunicorn with the Uvicorn worker:
   ```
   gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:$PORT
   ```
5. Set the application settings the app reads from the environment. `.env` is not
   deployed, so anything only in that file is absent in production:
   ```bash
   az webapp config appsettings set -n <app-service-name> -g <resource-group> \
     --settings AZURE_FORECAST_ENDPOINT="<scoring uri>" AZURE_FORECAST_KEY="<key>"
   ```
   These two are optional. Without them the revenue forecast is served by the model
   committed at `backend/models/revenue_model.joblib` instead of the Azure ML endpoint —
   a working forecast, just a less accurate one. Nothing fails and nothing is logged at
   startup, so if the forecast should be coming from the endpoint, check these are set.

## Frontend build

```bash
cd frontend
npm install
npm run build
```

Copy the contents of `frontend/dist/` into `backend/static/` before running `make-deploy-zip.py`. The backend serves this directory directly at `/assets` and falls back to `index.html` for client-side routes, so React Router works correctly on a direct page load or refresh.

## Dependency installation

Backend:
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

Frontend: see "Frontend build" above.

## Starting and verifying the application

Local development:
```bash
# backend
cd backend
python -m app.main
# frontend (separate terminal)
cd frontend
npm run dev
```
The backend runs on `http://127.0.0.1:8000`; the frontend dev server is usually `http://localhost:5173`.

After deploying to Azure:
1. Check `https://<app-service-name>.azurewebsites.net/api/health` — should return `{"message": "Backend is running"}`.
2. Open the root URL to confirm the frontend loads and can log in.

## Azure Portal configuration notes

- Startup Command: App Service → Configuration → General settings → Startup Command (see step 4 above).
- Python version: Configuration → General settings → Stack settings → confirm Python 3.12.
- Database firewall: allow the App Service's outbound IP (or enable "Allow access to Azure services") on the Postgres Flexible Server's networking settings, or the backend won't be able to connect.

## Assumptions and limitations

- This is a single-instance manual deployment; there is no CI/CD pipeline by design.
- The frontend build output is not committed to the repository — it must be built and copied into `backend/static/` before each deployment.
- `backend-deploy.zip` is a local build artifact (git-ignored) — regenerate it with `make-deploy-zip.py` whenever you redeploy.

## Tests

Backend and shared mapping-logic tests (run from the repo root so `src/`
is importable):

```bash
pip install -r backend/requirements.txt
python -m pytest tests backend/tests
```

Frontend tests:

```bash
cd frontend
npm test
```

## Required versions

Backend:
- Python 3.12.x

Frontend:
- Node.js 22 LTS
- npm 10.x

Backend packages are pinned in `backend/requirements.txt`, and frontend package versions are listed in `frontend/package.json`.
