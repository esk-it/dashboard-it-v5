from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging
from .database import init_db, get_raw_db
from .routers import dashboard, tasks, settings, search, planning, documents, changelog, wiki, news, suppliers, parc, security, monitoring, tools, glpi, launcher, auth, projects, establishments, dossiers

logger = logging.getLogger(__name__)

# Import optional modules (may fail in PyInstaller if not bundled correctly)
try:
    from .routers import google_calendar
except Exception as e:
    google_calendar = None
    logger.error(f"Failed to import google_calendar router: {e}")

try:
    from .routers import gmail
except Exception as e:
    gmail = None
    logger.error(f"Failed to import gmail router: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables on startup (handles fresh installs)."""
    await init_db()
    # Ensure default admin user exists
    from .routers.auth import ensure_default_admin
    import aiosqlite
    from .database import DB_PATH
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await ensure_default_admin(db)
    yield


app = FastAPI(title="ITManager Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ────────────────────────────────────────────
# Lightweight ping so the UI can detect if the backend sidecar has crashed.
# Kept un-routed (top-level) so it has zero dependencies and stays cheap.
import time as _time
_BACKEND_STARTED_AT = _time.time()


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "uptime_seconds": int(_time.time() - _BACKEND_STARTED_AT),
    }

app.include_router(dashboard.router)
app.include_router(tasks.router)
app.include_router(settings.router)
app.include_router(search.router)
app.include_router(planning.router)
app.include_router(documents.router)
app.include_router(changelog.router)
app.include_router(wiki.router)
app.include_router(news.router)
app.include_router(suppliers.router)
app.include_router(parc.router)
app.include_router(security.router)
app.include_router(monitoring.router)
app.include_router(tools.router)
app.include_router(glpi.router)
app.include_router(launcher.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(establishments.router)
app.include_router(dossiers.router)
if google_calendar:
    app.include_router(google_calendar.router)
if gmail:
    app.include_router(gmail.router)
