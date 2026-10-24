import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth.middleware import JWTAuthMiddleware
from app.auth.router import router as auth_router
from app.chatbot.router import router as chatbot_router
from app.core.config import FRONTEND_ORIGIN
from app.dashboard.router import router as dashboard_router
from app.data_pipeline.mapping.router import router as mapping_router
from app.data_pipeline.upload.router import router as upload_router
from app.db.datasets_router import router as datasets_router
from app.forecast.router import router as forecast_router
from app.health.router import router as health_router
from app.recommendations.router import router as recommendations_router
from app.reports.router import router as reports_router

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

app = FastAPI()

app.add_middleware(JWTAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(mapping_router)
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(chatbot_router)
app.include_router(recommendations_router)
app.include_router(datasets_router)
app.include_router(forecast_router)
app.include_router(reports_router)

# Serve the built React SPA. Path is resolved from this file, not the process
# cwd, because Oryx extracts the app to a random /tmp/<hash> directory at
# container start.
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

if _STATIC_DIR.is_dir():
    # Hashed JS/CSS bundles only. Mounted at /assets (not "/") so it can't
    # swallow API routes or the SPA-fallback route below.
    app.mount(
        "/assets",
        StaticFiles(directory=str(_STATIC_DIR / "assets")),
        name="static-assets",
    )

    # SPA fallback: any GET that isn't an API route or a static asset gets
    # index.html, so React Router can handle client-side routes like /login,
    # /register, /profile on a direct page load or refresh.
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(_INDEX_HTML)


if __name__ == "__main__":
    import uvicorn

    from app.core.config import PORT

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=PORT,
        reload=True,
    )
