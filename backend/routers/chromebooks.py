"""Router Chromebooks (v7.2.0).

Mini-MDM dedicated to the teacher Chromebook fleet (~500 devices). Pulls from
Google Admin SDK Directory API and stores enriched local rows so the IT manager
can track lifecycle state (à rendre, rendu, en panne…) and end-of-year rotation
campaigns without leaving DashboardIT.

Sync policy:
  * INSERT/UPDATE per natural key — never DELETE. A device moved to a stock OU
    on Google's side stays visible locally with `binding_source` info preserved.
  * Auto-binding chromebook ↔ teacher resolves at every sync with this priority:
        annotatedUser  >  recentUsers[0].email  >  existing 'manual' binding
    If nothing matches, the device ends up `binding_source = 'none'` (orphan).
  * Whenever the resolved teacher changes between two syncs, we log a row in
    `chromebook_assignments_history` so the user gets a full audit trail.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..database import get_raw_db
from ..schemas.chromebook import (
    AssignmentHistoryEntry,
    ChromebookResponse,
    ChromebookUpdate,
    SyncStats,
)
from ..services import google_admin, google_calendar

router = APIRouter(prefix="/api/chromebooks", tags=["chromebooks"])


# ── Settings (OU paths) ───────────────────────────────────────────────────

if os.environ.get("ITMANAGER_DATA_DIR"):
    _DATA_DIR = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data"
else:
    _DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_SETTINGS_PATH = _DATA_DIR / "chromebook_settings.json"

_DEFAULT_SETTINGS = {
    # Path discovered with the user: lekreisker.fr > 1. Chromebooks > 1. Personnel éducatif.
    # API uses forward slashes from the customer root.
    "device_ou_path": "/1. Chromebooks/1. Personnel éducatif",
    # User OU is typically the same name without the "1. Chromebooks" prefix
    # (Google separates device OUs from user OUs). The user can adjust this
    # via the settings endpoint.
    "user_ou_path": "/1. Personnel éducatif",
    # When True, also fetch devices in child OUs. Off by default — explicit
    # OU is safer for the user's mental model.
    "include_device_descendants": False,
}


def _load_settings() -> dict:
    if not _SETTINGS_PATH.exists():
        return dict(_DEFAULT_SETTINGS)
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULT_SETTINGS, **data}
    except Exception:
        return dict(_DEFAULT_SETTINGS)


def _save_settings(data: dict) -> None:
    cur = _load_settings()
    cur.update({k: v for k, v in data.items() if k in _DEFAULT_SETTINGS})
    _SETTINGS_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("/settings")
async def get_chromebook_settings():
    cfg = _load_settings()
    cfg["google_connected"] = google_calendar.is_connected()
    return cfg


@router.put("/settings")
async def update_chromebook_settings(body: dict = Body(...)):
    _save_settings(body or {})
    return _load_settings()


# ── DB helpers ────────────────────────────────────────────────────────────

_CB_COLS = """
    c.id, c.google_device_id, c.serial_number, c.model, c.annotated_asset_id,
    c.annotated_user, c.org_unit_path, c.google_status, c.last_enrollment_time,
    c.support_end_date, c.last_user_email, c.assigned_teacher_id,
    c.binding_source, c.status_local, c.service_start_date, c.return_date,
    c.notes_local, c.last_sync, c.created_at, c.updated_at,
    COALESCE(t.email,''), COALESCE(t.full_name,''), COALESCE(t.status_local,'')
"""

_CB_FROM = """
    FROM chromebooks c
    LEFT JOIN teachers t ON t.id = c.assigned_teacher_id
"""


def _row_to_chromebook(r) -> dict:
    return dict(
        id=r[0], google_device_id=r[1], serial_number=r[2], model=r[3],
        annotated_asset_id=r[4], annotated_user=r[5], org_unit_path=r[6],
        google_status=r[7], last_enrollment_time=r[8], support_end_date=r[9],
        last_user_email=r[10], assigned_teacher_id=r[11],
        binding_source=r[12], status_local=r[13], service_start_date=r[14],
        return_date=r[15], notes_local=r[16], last_sync=r[17],
        created_at=r[18], updated_at=r[19],
        teacher_email=r[20], teacher_full_name=r[21],
        teacher_status_local=r[22],
    )


# ── List / detail ─────────────────────────────────────────────────────────

@router.get("", response_model=list[ChromebookResponse])
async def list_chromebooks(
    search: str = Query(""),
    status_local: str = Query(""),
    model: str = Query(""),
    binding_source: str = Query(""),
    has_teacher: str = Query(""),  # 'true' / 'false' / ''
    teacher_id: int | None = Query(None),
    sort: str = Query("model"),  # model / serial / recent_sync / last_enrollment
    db=Depends(get_raw_db),
):
    where: list[str] = ["1=1"]
    params: list = []

    if search:
        like = f"%{search.lower()}%"
        where.append(
            "(LOWER(c.serial_number) LIKE ? OR LOWER(c.model) LIKE ? OR LOWER(c.annotated_asset_id) LIKE ?"
            " OR LOWER(c.annotated_user) LIKE ? OR LOWER(c.last_user_email) LIKE ?"
            " OR LOWER(COALESCE(t.full_name,'')) LIKE ? OR LOWER(COALESCE(t.email,'')) LIKE ?)"
        )
        params.extend([like] * 7)
    if status_local:
        where.append("c.status_local = ?")
        params.append(status_local)
    if model:
        where.append("c.model = ?")
        params.append(model)
    if binding_source:
        where.append("c.binding_source = ?")
        params.append(binding_source)
    if has_teacher == "true":
        where.append("c.assigned_teacher_id IS NOT NULL")
    elif has_teacher == "false":
        where.append("c.assigned_teacher_id IS NULL")
    if teacher_id is not None:
        where.append("c.assigned_teacher_id = ?")
        params.append(teacher_id)

    order_by = {
        "model": "c.model ASC, c.serial_number ASC",
        "serial": "c.serial_number ASC",
        "recent_sync": "c.last_sync DESC",
        "last_enrollment": "c.last_enrollment_time DESC",
    }.get(sort, "c.model ASC, c.serial_number ASC")

    sql = f"SELECT {_CB_COLS} {_CB_FROM} WHERE {' AND '.join(where)} ORDER BY {order_by}"
    rows = await db.execute_fetchall(sql, params)
    return [ChromebookResponse(**_row_to_chromebook(r)) for r in rows]


@router.get("/models")
async def list_models(db=Depends(get_raw_db)):
    """Distinct model names — fuels the filter dropdown."""
    rows = await db.execute_fetchall(
        "SELECT DISTINCT model FROM chromebooks WHERE model <> '' ORDER BY model"
    )
    return [r[0] for r in rows]


@router.get("/stats")
async def chromebook_stats(db=Depends(get_raw_db)):
    """Top-level KPIs for the dashboard / page header."""
    total = (await (await db.execute("SELECT COUNT(*) FROM chromebooks")).fetchone())[0]
    by_status: dict[str, int] = {}
    rows = await db.execute_fetchall(
        "SELECT status_local, COUNT(*) FROM chromebooks GROUP BY status_local"
    )
    for s, n in rows:
        by_status[s or ""] = n
    orphans = (await (await db.execute(
        "SELECT COUNT(*) FROM chromebooks WHERE assigned_teacher_id IS NULL"
    )).fetchone())[0]
    teachers_no_device = (await (await db.execute(
        "SELECT COUNT(*) FROM teachers t WHERE NOT EXISTS "
        "(SELECT 1 FROM chromebooks c WHERE c.assigned_teacher_id = t.id)"
    )).fetchone())[0]
    last_sync_row = await db.execute_fetchall(
        "SELECT MAX(last_sync) FROM chromebooks"
    )
    last_sync = last_sync_row[0][0] if last_sync_row else ""
    return {
        "total": total,
        "by_status_local": by_status,
        "orphans": orphans,
        "teachers_no_device": teachers_no_device,
        "last_sync": last_sync or "",
    }


@router.get("/{cb_id}", response_model=ChromebookResponse)
async def get_chromebook(cb_id: int, db=Depends(get_raw_db)):
    sql = f"SELECT {_CB_COLS} {_CB_FROM} WHERE c.id = ?"
    rows = await db.execute_fetchall(sql, (cb_id,))
    if not rows:
        raise HTTPException(404, "Chromebook introuvable")
    return ChromebookResponse(**_row_to_chromebook(rows[0]))


@router.get("/{cb_id}/history", response_model=list[AssignmentHistoryEntry])
async def chromebook_history(cb_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        """SELECT id, chromebook_id, teacher_id, teacher_email, teacher_name,
                  assigned_at, returned_at, condition_in, condition_out, notes
           FROM chromebook_assignments_history
           WHERE chromebook_id = ?
           ORDER BY assigned_at DESC, id DESC""",
        (cb_id,),
    )
    return [
        AssignmentHistoryEntry(
            id=r[0], chromebook_id=r[1], teacher_id=r[2],
            teacher_email=r[3] or "", teacher_name=r[4] or "",
            assigned_at=r[5], returned_at=r[6],
            condition_in=r[7] or "", condition_out=r[8] or "",
            notes=r[9] or "",
        )
        for r in rows
    ]


# ── Update (local fields + manual rebind) ─────────────────────────────────

@router.patch("/{cb_id}", response_model=ChromebookResponse)
async def update_chromebook(
    cb_id: int,
    body: ChromebookUpdate,
    db=Depends(get_raw_db),
):
    rows = await db.execute_fetchall(
        "SELECT id, assigned_teacher_id, binding_source FROM chromebooks WHERE id = ?",
        (cb_id,),
    )
    if not rows:
        raise HTTPException(404, "Chromebook introuvable")
    _, current_teacher_id, _ = rows[0]

    payload = body.model_dump(exclude_unset=True)
    clear = payload.pop("clear_assignment", False)
    sets: list[str] = []
    params: list = []

    if "status_local" in payload:
        sets.append("status_local = ?")
        params.append(payload["status_local"] or "en_service")
        # When user marks "rendu", auto-fill return_date if not set yet.
        if payload["status_local"] == "rendu" and not payload.get("return_date"):
            sets.append(
                "return_date = COALESCE(return_date, ?)"
            )
            params.append(datetime.now().strftime("%Y-%m-%d"))
    if "service_start_date" in payload:
        sets.append("service_start_date = ?")
        params.append(payload["service_start_date"] or None)
    if "return_date" in payload:
        sets.append("return_date = ?")
        params.append(payload["return_date"] or None)
    if "notes_local" in payload:
        sets.append("notes_local = ?")
        params.append(payload["notes_local"] or "")

    # Manual rebind — overrides whatever auto-binding decided.
    rebind = False
    new_teacher_id: int | None = current_teacher_id
    if clear:
        new_teacher_id = None
        rebind = True
    elif "assigned_teacher_id" in payload:
        new_teacher_id = payload["assigned_teacher_id"]
        rebind = True

    if rebind:
        sets.append("assigned_teacher_id = ?")
        params.append(new_teacher_id)
        sets.append("binding_source = ?")
        params.append("manual")
        # Log assignment history if the teacher actually changed
        if new_teacher_id != current_teacher_id:
            await _log_binding_change(
                db, cb_id, current_teacher_id, new_teacher_id,
                note="Modification manuelle depuis l'interface",
            )

    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat(timespec="seconds"))
    params.append(cb_id)

    if sets:
        await db.execute(f"UPDATE chromebooks SET {', '.join(sets)} WHERE id = ?", params)
        await db.commit()

    sql = f"SELECT {_CB_COLS} {_CB_FROM} WHERE c.id = ?"
    rows = await db.execute_fetchall(sql, (cb_id,))
    return ChromebookResponse(**_row_to_chromebook(rows[0]))


async def _log_binding_change(
    db, cb_id: int, old_teacher_id: int | None, new_teacher_id: int | None, *,
    note: str = "",
) -> None:
    """Close the previous assignment row (if any) and open a new one."""
    now = datetime.now().isoformat(timespec="seconds")
    # Close the previous open assignment
    if old_teacher_id is not None:
        await db.execute(
            """UPDATE chromebook_assignments_history
               SET returned_at = ?
               WHERE chromebook_id = ?
                 AND teacher_id = ?
                 AND (returned_at IS NULL OR returned_at = '')""",
            (now, cb_id, old_teacher_id),
        )
    # Open the new assignment
    if new_teacher_id is not None:
        rows = await db.execute_fetchall(
            "SELECT email, full_name FROM teachers WHERE id = ?",
            (new_teacher_id,),
        )
        email = rows[0][0] if rows else ""
        name = rows[0][1] if rows else ""
        await db.execute(
            """INSERT INTO chromebook_assignments_history
               (chromebook_id, teacher_id, teacher_email, teacher_name,
                assigned_at, returned_at, condition_in, condition_out, notes)
               VALUES (?, ?, ?, ?, ?, NULL, '', '', ?)""",
            (cb_id, new_teacher_id, email, name, now, note),
        )


# ── Sync from Google Admin SDK ────────────────────────────────────────────

@router.post("/sync", response_model=SyncStats)
async def sync_from_google(db=Depends(get_raw_db)):
    """Pull devices + teachers from Google Admin and reconcile locally.

    Two-phase to keep auto-binding straightforward:
      Phase 1 — upsert teachers (so device lookup by email always succeeds)
      Phase 2 — upsert devices and resolve teacher binding
    """
    if not google_calendar.is_connected():
        raise HTTPException(
            400,
            "Google n'est pas connecté. Va dans Paramètres → Google pour "
            "te connecter (les scopes Admin Directory ont été ajoutés en v7.2.0).",
        )

    settings = _load_settings()
    device_ou = (settings.get("device_ou_path") or "").strip()
    user_ou = (settings.get("user_ou_path") or "").strip()
    if not device_ou or not user_ou:
        raise HTTPException(
            400,
            "Configure d'abord les OU côté Paramètres Chromebooks.",
        )

    started = datetime.now()
    t0 = time.monotonic()
    stats = SyncStats(started_at=started.isoformat(timespec="seconds"))
    now_iso = started.isoformat(timespec="seconds")

    # ── Phase 1 — Teachers ─────────────────────────────────────────────
    try:
        users_raw = await google_admin.fetch_users(user_ou)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        stats.errors.append(f"fetch_users: {e!s}")
        users_raw = []

    teacher_by_email: dict[str, int] = {}
    for raw in users_raw:
        norm = google_admin.normalize_user(raw)
        email = norm["email"]
        if not email:
            continue

        existing = await db.execute_fetchall(
            "SELECT id FROM teachers WHERE email = ?", (email,)
        )
        if existing:
            tid = existing[0][0]
            await db.execute(
                """UPDATE teachers
                   SET google_user_id = ?, full_name = ?, given_name = ?,
                       family_name = ?, google_ou_path = ?, is_suspended = ?,
                       last_sync = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    norm["google_user_id"], norm["full_name"], norm["given_name"],
                    norm["family_name"], norm["google_ou_path"], norm["is_suspended"],
                    now_iso, now_iso, tid,
                ),
            )
            stats.teachers_updated += 1
        else:
            cur = await db.execute(
                """INSERT INTO teachers
                   (google_user_id, email, full_name, given_name, family_name,
                    google_ou_path, is_suspended, status_local, notes,
                    last_sync, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'present', '', ?, ?, ?)""",
                (
                    norm["google_user_id"], email, norm["full_name"],
                    norm["given_name"], norm["family_name"], norm["google_ou_path"],
                    norm["is_suspended"], now_iso, now_iso, now_iso,
                ),
            )
            tid = cur.lastrowid
            stats.teachers_inserted += 1
        teacher_by_email[email] = tid
    stats.teachers_total = len(users_raw)
    await db.commit()

    # Build a complete email→id map (existing + just-synced) for binding.
    all_teachers = await db.execute_fetchall(
        "SELECT id, LOWER(email) FROM teachers WHERE email <> ''"
    )
    teacher_by_email = {email: tid for tid, email in all_teachers}

    # ── Phase 2 — Devices ──────────────────────────────────────────────
    try:
        devices_raw = await google_admin.fetch_chromeos_devices(
            device_ou,
            include_descendants=bool(settings.get("include_device_descendants")),
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        stats.errors.append(f"fetch_chromeos_devices: {e!s}")
        devices_raw = []

    for raw in devices_raw:
        norm = google_admin.normalize_chromeos_device(raw)
        device_id = norm["google_device_id"]
        if not device_id:
            continue

        existing = await db.execute_fetchall(
            "SELECT id, assigned_teacher_id, binding_source FROM chromebooks WHERE google_device_id = ?",
            (device_id,),
        )

        # Resolve binding
        annotated = (norm["annotated_user"] or "").lower()
        last_user = (norm["last_user_email"] or "").lower()
        binding_source = "none"
        teacher_id: int | None = None
        if annotated and annotated in teacher_by_email:
            teacher_id = teacher_by_email[annotated]
            binding_source = "annotated"
        elif last_user and last_user in teacher_by_email:
            teacher_id = teacher_by_email[last_user]
            binding_source = "recent_user"

        if existing:
            cb_id, old_teacher_id, old_source = existing[0]
            # Honour manual overrides: if the user previously bound manually
            # (or explicitly cleared), don't auto-rebind in sync.
            if old_source == "manual":
                teacher_id = old_teacher_id
                binding_source = "manual"
            await db.execute(
                """UPDATE chromebooks SET
                       serial_number = ?, model = ?, annotated_asset_id = ?,
                       annotated_user = ?, org_unit_path = ?, google_status = ?,
                       last_enrollment_time = ?, support_end_date = ?,
                       last_user_email = ?, assigned_teacher_id = ?,
                       binding_source = ?, last_sync = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    norm["serial_number"], norm["model"], norm["annotated_asset_id"],
                    norm["annotated_user"], norm["org_unit_path"], norm["google_status"],
                    norm["last_enrollment_time"], norm["support_end_date"],
                    norm["last_user_email"], teacher_id,
                    binding_source, now_iso, now_iso, cb_id,
                ),
            )
            stats.devices_updated += 1
            if teacher_id != old_teacher_id:
                stats.devices_rebound += 1
                await _log_binding_change(
                    db, cb_id, old_teacher_id, teacher_id,
                    note=f"Sync auto ({binding_source})",
                )
        else:
            cur = await db.execute(
                """INSERT INTO chromebooks
                   (google_device_id, serial_number, model, annotated_asset_id,
                    annotated_user, org_unit_path, google_status,
                    last_enrollment_time, support_end_date, last_user_email,
                    assigned_teacher_id, binding_source, status_local,
                    notes_local, last_sync, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'en_service', '', ?, ?, ?)""",
                (
                    device_id, norm["serial_number"], norm["model"],
                    norm["annotated_asset_id"], norm["annotated_user"],
                    norm["org_unit_path"], norm["google_status"],
                    norm["last_enrollment_time"], norm["support_end_date"],
                    norm["last_user_email"], teacher_id, binding_source,
                    now_iso, now_iso, now_iso,
                ),
            )
            cb_id = cur.lastrowid
            stats.devices_inserted += 1
            if teacher_id is not None:
                await _log_binding_change(
                    db, cb_id, None, teacher_id,
                    note=f"Sync auto (initial, {binding_source})",
                )

        if binding_source == "none":
            stats.devices_orphaned += 1

    stats.devices_total = len(devices_raw)
    await db.commit()

    finished = datetime.now()
    stats.finished_at = finished.isoformat(timespec="seconds")
    stats.duration_seconds = round(time.monotonic() - t0, 2)
    return stats
