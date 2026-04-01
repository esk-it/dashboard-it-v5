"""Google Calendar bidirectional sync service.

OAuth2 "Desktop App" flow using raw httpx (no google-auth dependency).
Config stored in backend/data/google_calendar_config.json.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

if os.environ.get("ITMANAGER_DATA_DIR"):
    DATA_DIR = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data"
else:
    DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA_DIR / "google_calendar_config.json"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPES = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events"
REDIRECT_URI = "http://localhost:8010/api/google-calendar/oauth/callback"

# Temporary storage for PKCE code_verifier (in-memory, per-session)
_pending_verifier: str | None = None


# ── Config management ────────────────────────────────────────────


def load_config() -> dict | None:
    """Load config. Returns dict if file exists with at least client_id, or None."""
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if data.get("client_id"):
            return data
    except Exception:
        pass
    return None


def save_config(data: dict) -> None:
    existing = load_config() or {}
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def delete_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def get_masked_config() -> dict | None:
    cfg = load_config()
    if not cfg:
        return None
    masked = {**cfg}
    for key in ("access_token", "refresh_token", "client_secret"):
        if masked.get(key):
            val = masked[key]
            masked[key] = f"{'*' * 8}{val[-4:]}" if len(val) > 4 else "****"
    return masked


def is_connected() -> bool:
    cfg = load_config()
    return cfg is not None and bool(cfg.get("refresh_token"))


# ── OAuth2 flow ──────────────────────────────────────────────────


def get_auth_url(client_id: str, client_secret: str) -> str:
    """Build Google OAuth2 authorization URL with PKCE."""
    global _pending_verifier
    _pending_verifier = secrets.token_urlsafe(64)

    # PKCE code challenge (S256)
    digest = hashlib.sha256(_pending_verifier.encode()).digest()
    import base64
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    # Save client credentials for later exchange
    save_config({"client_id": client_id, "client_secret": client_secret})

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Exchange authorization code for tokens and fetch user email."""
    global _pending_verifier
    cfg = load_config()
    if not cfg:
        raise ValueError("No config found — start auth first")

    payload = {
        "code": code,
        "client_id": cfg["client_id"],
        "client_secret": cfg.get("client_secret", ""),
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    if _pending_verifier:
        payload["code_verifier"] = _pending_verifier
        _pending_verifier = None

    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
        resp.raise_for_status()
        tokens = resp.json()

    # Calculate expiry
    expires_in = tokens.get("expires_in", 3600)
    token_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    # Fetch user email
    email = ""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if resp.status_code == 200:
                email = resp.json().get("email", "")
    except Exception:
        pass

    save_config({
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", cfg.get("refresh_token", "")),
        "token_expiry": token_expiry,
        "connected_email": email,
        "calendar_id": cfg.get("calendar_id", "primary"),
    })

    return {"email": email, "connected": True}


async def _ensure_valid_token() -> str:
    """Return a valid access token, refreshing if expired."""
    cfg = load_config()
    if not cfg:
        raise ValueError("Google Calendar not configured")

    expiry = cfg.get("token_expiry", "")
    if expiry:
        try:
            exp_dt = datetime.fromisoformat(expiry)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < exp_dt - timedelta(minutes=2):
                return cfg["access_token"]
        except Exception:
            pass

    # Refresh
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": cfg["client_id"],
            "client_secret": cfg.get("client_secret", ""),
            "refresh_token": cfg["refresh_token"],
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = tokens.get("expires_in", 3600)
    token_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    save_config({
        "access_token": tokens["access_token"],
        "token_expiry": token_expiry,
    })
    return tokens["access_token"]


# ── Google Calendar API calls ────────────────────────────────────


async def list_calendars() -> list[dict]:
    """List all calendars for the authenticated user."""
    token = await _ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GOOGLE_CALENDAR_API}/users/me/calendarList",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    items = resp.json().get("items", [])
    return [{"id": c["id"], "summary": c.get("summary", ""), "primary": c.get("primary", False)} for c in items]


async def list_events(
    time_min: str | None = None,
    time_max: str | None = None,
    sync_token: str | None = None,
) -> dict:
    """Fetch events from Google Calendar. Uses syncToken for incremental sync."""
    token = await _ensure_valid_token()
    cfg = load_config()
    calendar_id = cfg.get("calendar_id", "primary")

    params: dict = {"maxResults": 250, "singleEvents": True, "orderBy": "startTime"}
    if sync_token:
        params = {"syncToken": sync_token}
    else:
        if time_min:
            params["timeMin"] = f"{time_min}T00:00:00Z"
        if time_max:
            params["timeMax"] = f"{time_max}T23:59:59Z"

    all_items = []
    next_page = None
    next_sync_token = None

    async with httpx.AsyncClient() as client:
        while True:
            if next_page:
                params["pageToken"] = next_page
            resp = await client.get(
                f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if resp.status_code == 410:
                # syncToken expired — do full sync
                return await list_events(time_min=time_min, time_max=time_max, sync_token=None)
            resp.raise_for_status()
            data = resp.json()
            all_items.extend(data.get("items", []))
            next_page = data.get("nextPageToken")
            next_sync_token = data.get("nextSyncToken")
            if not next_page:
                break

    return {"items": all_items, "nextSyncToken": next_sync_token}


async def create_google_event(event_body: dict) -> dict:
    """Create an event on Google Calendar."""
    token = await _ensure_valid_token()
    cfg = load_config()
    calendar_id = cfg.get("calendar_id", "primary")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_body,
        )
        resp.raise_for_status()
    return resp.json()


async def update_google_event(event_id: str, event_body: dict) -> dict:
    """Update an event on Google Calendar."""
    token = await _ensure_valid_token()
    cfg = load_config()
    calendar_id = cfg.get("calendar_id", "primary")
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_body,
        )
        resp.raise_for_status()
    return resp.json()


async def delete_google_event(event_id: str) -> None:
    """Delete an event from Google Calendar."""
    token = await _ensure_valid_token()
    cfg = load_config()
    calendar_id = cfg.get("calendar_id", "primary")
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code not in (204, 410, 404):
            resp.raise_for_status()


# ── Event mapping ────────────────────────────────────────────────


def itm_to_google(evt: dict) -> dict:
    """Convert ITManager planning event to Google Calendar event body."""
    body: dict = {
        "summary": evt.get("title", ""),
        "description": evt.get("notes", ""),
        "extendedProperties": {
            "private": {
                "itm_event_type": evt.get("event_type", "other"),
                "itm_person": evt.get("person", ""),
            }
        },
    }
    if evt.get("all_day"):
        body["start"] = {"date": evt["date_start"]}
        # Google all-day end is exclusive
        end_date = evt.get("date_end", evt["date_start"])
        from datetime import date as date_cls
        d = date_cls.fromisoformat(end_date) + timedelta(days=1)
        body["end"] = {"date": d.isoformat()}
    else:
        tz = "Europe/Paris"
        body["start"] = {"dateTime": f"{evt['date_start']}T{evt.get('time_start', '09:00')}:00", "timeZone": tz}
        body["end"] = {"dateTime": f"{evt.get('date_end', evt['date_start'])}T{evt.get('time_end', '10:00')}:00", "timeZone": tz}
    return body


def google_to_itm(gcal: dict) -> dict:
    """Convert Google Calendar event to ITManager planning event fields."""
    start = gcal.get("start", {})
    end = gcal.get("end", {})
    ext = gcal.get("extendedProperties", {}).get("private", {})

    all_day = "date" in start
    if all_day:
        date_start = start["date"]
        # Google end date is exclusive for all-day
        end_date = end.get("date", date_start)
        from datetime import date as date_cls
        d = date_cls.fromisoformat(end_date) - timedelta(days=1)
        date_end = d.isoformat()
        time_start = None
        time_end = None
    else:
        dt_start = start.get("dateTime", "")
        dt_end = end.get("dateTime", "")
        date_start = dt_start[:10] if dt_start else ""
        date_end = dt_end[:10] if dt_end else date_start
        time_start = dt_start[11:16] if len(dt_start) >= 16 else "09:00"
        time_end = dt_end[11:16] if len(dt_end) >= 16 else "10:00"

    return {
        "title": gcal.get("summary", "(sans titre)"),
        "event_type": ext.get("itm_event_type", "other"),
        "date_start": date_start,
        "date_end": date_end,
        "all_day": all_day,
        "time_start": time_start,
        "time_end": time_end,
        "person": ext.get("itm_person", ""),
        "notes": gcal.get("description", ""),
        "google_event_id": gcal.get("id", ""),
        "google_updated_at": gcal.get("updated", ""),
    }


# ── Bidirectional sync ───────────────────────────────────────────


async def sync_bidirectional(db) -> dict:
    """Run bidirectional sync. Returns stats dict."""
    cfg = load_config()
    if not cfg or not cfg.get("refresh_token"):
        raise ValueError("Google Calendar not connected")

    now = datetime.now(timezone.utc).isoformat()
    sync_token = cfg.get("sync_token")
    stats = {"imported": 0, "exported": 0, "updated": 0, "deleted": 0}

    # ── 1. Fetch Google changes ──
    if sync_token:
        result = await list_events(sync_token=sync_token)
    else:
        # First sync: past 3 months to future 6 months
        t_min = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        t_max = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
        result = await list_events(time_min=t_min, time_max=t_max)

    google_events = result.get("items", [])
    new_sync_token = result.get("nextSyncToken")

    # ── 2. Process Google events ──
    for g_evt in google_events:
        g_id = g_evt.get("id", "")
        if not g_id:
            continue

        # Check if cancelled (deleted on Google side)
        if g_evt.get("status") == "cancelled":
            rows = await db.execute_fetchall(
                "SELECT id FROM planning_events WHERE google_event_id = ?", (g_id,)
            )
            if rows:
                await db.execute("DELETE FROM planning_events WHERE google_event_id = ?", (g_id,))
                stats["deleted"] += 1
            continue

        # Skip recurring event masters (only sync single instances)
        if g_evt.get("recurrence"):
            continue

        itm_data = google_to_itm(g_evt)

        # Check if we already have this event locally
        rows = await db.execute_fetchall(
            "SELECT id, google_updated_at FROM planning_events WHERE google_event_id = ?",
            (g_id,),
        )
        if rows:
            local_id = rows[0][0]
            local_updated = rows[0][1] or ""
            google_updated = g_evt.get("updated", "")
            # Last-write-wins
            if google_updated > local_updated:
                await db.execute(
                    """UPDATE planning_events
                       SET title=?, event_type=?, date_start=?, date_end=?,
                           all_day=?, time_start=?, time_end=?, person=?, notes=?,
                           google_updated_at=?
                       WHERE id=?""",
                    (
                        itm_data["title"], itm_data["event_type"],
                        itm_data["date_start"], itm_data["date_end"],
                        int(itm_data["all_day"]), itm_data["time_start"], itm_data["time_end"],
                        itm_data["person"], itm_data["notes"],
                        google_updated, local_id,
                    ),
                )
                stats["updated"] += 1
        else:
            # New event from Google — import
            created_at = datetime.now().isoformat(timespec="seconds")
            await db.execute(
                """INSERT INTO planning_events
                   (title, event_type, date_start, date_end, all_day,
                    time_start, time_end, person, notes, task_id,
                    created_at, google_event_id, google_updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
                (
                    itm_data["title"], itm_data["event_type"],
                    itm_data["date_start"], itm_data["date_end"],
                    int(itm_data["all_day"]), itm_data["time_start"], itm_data["time_end"],
                    itm_data["person"], itm_data["notes"],
                    created_at, g_id, g_evt.get("updated", ""),
                ),
            )
            stats["imported"] += 1

    # ── 3. Push local events to Google ──
    rows = await db.execute_fetchall(
        """SELECT id, title, event_type, date_start, date_end,
                  all_day, time_start, time_end, person, notes,
                  google_event_id, google_updated_at
           FROM planning_events
           WHERE google_event_id IS NULL OR google_event_id = ''"""
    )
    for row in rows:
        evt = {
            "id": row[0], "title": row[1], "event_type": row[2],
            "date_start": row[3], "date_end": row[4],
            "all_day": bool(row[5]), "time_start": row[6], "time_end": row[7],
            "person": row[8] or "", "notes": row[9] or "",
        }
        try:
            g_body = itm_to_google(evt)
            created = await create_google_event(g_body)
            g_id = created.get("id", "")
            g_updated = created.get("updated", now)
            await db.execute(
                "UPDATE planning_events SET google_event_id=?, google_updated_at=? WHERE id=?",
                (g_id, g_updated, evt["id"]),
            )
            stats["exported"] += 1
        except Exception as e:
            logger.warning(f"Failed to push event {evt['id']} to Google: {e}")

    # ── 4. Save sync token ──
    if new_sync_token:
        save_config({"sync_token": new_sync_token, "last_sync": now})

    await db.commit()
    return stats
