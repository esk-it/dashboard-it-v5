"""Google Calendar integration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..database import get_raw_db
from ..services import google_calendar as gcal

router = APIRouter(prefix="/api/google-calendar", tags=["google-calendar"])


# ── Schemas ──────────────────────────────────────────────────────


class AuthStartRequest(BaseModel):
    client_id: str
    client_secret: str


class CalendarSelectRequest(BaseModel):
    calendar_id: str


# ── Endpoints ────────────────────────────────────────────────────


@router.get("/config")
async def get_config():
    """Return connection status and masked config."""
    masked = gcal.get_masked_config()
    if not masked:
        return {"connected": False}
    return {
        "connected": gcal.is_connected(),
        "email": masked.get("connected_email", ""),
        "calendar_id": masked.get("calendar_id", "primary"),
        "last_sync": masked.get("last_sync"),
        **{k: v for k, v in masked.items() if k not in ("access_token", "refresh_token")},
    }


@router.post("/auth/start")
async def auth_start(body: AuthStartRequest):
    """Start OAuth2 flow. Returns auth URL to open in browser."""
    url = gcal.get_auth_url(body.client_id, body.client_secret)
    return {"auth_url": url}


@router.get("/oauth/callback")
async def oauth_callback(code: str = "", error: str = ""):
    """OAuth2 redirect callback — hit by the browser after Google login."""
    if error:
        return HTMLResponse(f"""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#e53e3e">Erreur de connexion</h2>
            <p>{error}</p>
            <p>Vous pouvez fermer cet onglet.</p>
            </body></html>
        """)

    try:
        result = await gcal.exchange_code(code)
        email = result.get("email", "")
        return HTMLResponse(f"""
            <html><body style="font-family:'Poppins',sans-serif;text-align:center;padding:60px;background:#151C2C;color:#fff">
            <h2 style="color:#22C55E">✅ Connecte a Google Calendar !</h2>
            <p>Compte : <strong>{email}</strong></p>
            <p style="color:#999;margin-top:2rem">Vous pouvez fermer cet onglet et retourner dans ITManager.</p>
            </body></html>
        """)
    except Exception as e:
        return HTMLResponse(f"""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px">
            <h2 style="color:#e53e3e">Erreur</h2>
            <p>{str(e)}</p>
            </body></html>
        """)


@router.delete("/config")
async def disconnect(db=Depends(get_raw_db)):
    """Disconnect Google Calendar and clear sync data."""
    # Clear google_event_id on all events
    await db.execute("UPDATE planning_events SET google_event_id = NULL, google_updated_at = NULL")
    await db.commit()
    gcal.delete_config()
    return {"disconnected": True}


@router.get("/calendars")
async def list_calendars():
    """List available Google Calendars for the authenticated user."""
    calendars = await gcal.list_calendars()
    return {"calendars": calendars}


@router.put("/calendar")
async def select_calendar(body: CalendarSelectRequest):
    """Select which Google Calendar to sync with."""
    gcal.save_config({"calendar_id": body.calendar_id})
    return {"calendar_id": body.calendar_id}


@router.post("/sync")
async def sync(db=Depends(get_raw_db)):
    """Trigger bidirectional sync."""
    stats = await gcal.sync_bidirectional(db)
    return stats


@router.get("/stats")
async def stats():
    """Return sync stats."""
    cfg = gcal.load_config()
    if not cfg:
        return {"connected": False}
    return {
        "connected": gcal.is_connected(),
        "email": cfg.get("connected_email", ""),
        "calendar_id": cfg.get("calendar_id", "primary"),
        "last_sync": cfg.get("last_sync"),
    }
