from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..database import get_raw_db
from ..services import google_calendar as gcal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/planning", tags=["planning"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PlanningEventCreate(BaseModel):
    title: str
    event_type: str = "other"
    date_start: str
    date_end: str
    all_day: bool = True
    time_start: str | None = None
    time_end: str | None = None
    person: str = ""
    notes: str = ""
    task_id: int | None = None
    site: str = ""  # establishment code (NDK / SU / NDE) or empty


class PlanningEventUpdate(BaseModel):
    title: str | None = None
    event_type: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    all_day: bool | None = None
    time_start: str | None = None
    time_end: str | None = None
    person: str | None = None
    notes: str | None = None
    task_id: int | None = None
    site: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_event(r) -> dict:
    return {
        "id": r[0],
        "title": r[1],
        "event_type": r[2] or "other",
        "date_start": r[3],
        "date_end": r[4],
        "all_day": bool(r[5]),
        "time_start": r[6],
        "time_end": r[7],
        "person": r[8] or "",
        "notes": r[9] or "",
        "task_id": r[10],
        "created_at": r[11] or "",
        "google_event_id": r[12] if len(r) > 12 else None,
        "google_updated_at": r[13] if len(r) > 13 else None,
        "site": r[14] if len(r) > 14 else "",
    }


_SELECT_COLS = """id, title, COALESCE(event_type,'other'), date_start, date_end,
                  all_day, time_start, time_end,
                  COALESCE(person,''), COALESCE(notes,''),
                  task_id, COALESCE(created_at,''),
                  google_event_id, google_updated_at,
                  COALESCE(site,'')"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/events")
async def list_events(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    db=Depends(get_raw_db),
):
    """Return events whose date range overlaps [start, end]."""
    rows = await db.execute_fetchall(
        f"""SELECT {_SELECT_COLS}
            FROM planning_events
            WHERE date_start <= ? AND date_end >= ?
            ORDER BY date_start ASC, time_start ASC NULLS LAST""",
        (end, start),
    )
    return [_row_to_event(r) for r in rows]


@router.get("/events/{event_id}")
async def get_event(event_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        f"SELECT {_SELECT_COLS} FROM planning_events WHERE id = ?",
        (event_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found")
    return _row_to_event(rows[0])


@router.post("/events", status_code=201)
async def create_event(body: PlanningEventCreate, db=Depends(get_raw_db)):
    now = datetime.now().isoformat(timespec="seconds")
    cursor = await db.execute(
        """INSERT INTO planning_events
           (title, event_type, date_start, date_end, all_day,
            time_start, time_end, person, notes, task_id, site, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            body.title,
            body.event_type,
            body.date_start,
            body.date_end,
            int(body.all_day),
            body.time_start,
            body.time_end,
            body.person,
            body.notes,
            body.task_id,
            body.site,
            now,
        ),
    )
    await db.commit()
    event_id = cursor.lastrowid

    # Push to Google Calendar if connected
    if gcal.is_connected():
        try:
            evt_data = {
                "title": body.title, "event_type": body.event_type,
                "date_start": body.date_start, "date_end": body.date_end,
                "all_day": body.all_day, "time_start": body.time_start,
                "time_end": body.time_end, "person": body.person, "notes": body.notes,
            }
            g_body = gcal.itm_to_google(evt_data)
            created = await gcal.create_google_event(g_body)
            g_id = created.get("id", "")
            g_updated = created.get("updated", "")
            await db.execute(
                "UPDATE planning_events SET google_event_id=?, google_updated_at=? WHERE id=?",
                (g_id, g_updated, event_id),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Google Calendar push failed for new event {event_id}: {e}")

    return await get_event(event_id, db)


@router.put("/events/{event_id}")
async def update_event(event_id: int, body: PlanningEventUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM planning_events WHERE id = ?", (event_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build partial update — only SET fields that were actually sent
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return await get_event(event_id, db)

    # Convert all_day bool to int for SQLite
    if "all_day" in updates:
        updates["all_day"] = int(updates["all_day"])

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [event_id]

    await db.execute(
        f"UPDATE planning_events SET {set_clause} WHERE id=?",
        values,
    )
    await db.commit()

    # Push update to Google Calendar if connected and event is synced
    if gcal.is_connected():
        try:
            evt = await get_event(event_id, db)
            g_id = evt.get("google_event_id")
            if g_id:
                g_body = gcal.itm_to_google_full(evt)
                result = await gcal.update_google_event(g_id, g_body)
                g_updated = result.get("updated", "")
                await db.execute(
                    "UPDATE planning_events SET google_updated_at=? WHERE id=?",
                    (g_updated, event_id),
                )
                await db.commit()
        except Exception as e:
            logger.warning(f"Google Calendar push failed for update event {event_id}: {e}")

    return await get_event(event_id, db)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, google_event_id FROM planning_events WHERE id = ?", (event_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Event not found")

    # Delete from Google Calendar if synced
    g_id = rows[0][1]
    if g_id and gcal.is_connected():
        try:
            await gcal.delete_google_event(g_id)
        except Exception as e:
            logger.warning(f"Google Calendar delete failed for event {event_id}: {e}")

    await db.execute("DELETE FROM planning_events WHERE id = ?", (event_id,))
    await db.commit()


@router.get("/tasks-for-calendar")
async def tasks_for_calendar(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    db=Depends(get_raw_db),
):
    """Return open tasks with a due_date inside [start, end]."""
    rows = await db.execute_fetchall(
        """SELECT id, title, COALESCE(category,''), priority, due_date,
                  done, COALESCE(site,'')
           FROM tasks
           WHERE due_date IS NOT NULL
             AND due_date >= ? AND due_date <= ?
             AND done = 0
           ORDER BY due_date ASC, priority ASC""",
        (start, end),
    )
    return [
        {
            "id": r[0],
            "title": r[1],
            "category": r[2],
            "priority": r[3],
            "due_date": r[4],
            "done": bool(r[5]),
            "site": r[6],
        }
        for r in rows
    ]
