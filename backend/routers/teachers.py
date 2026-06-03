"""Router Teachers (v7.2.0) — companion to chromebooks.

List/detail/edit of the Workspace teacher accounts mirrored in the local
`teachers` table. The sync from Google is triggered by the chromebooks router
(`POST /api/chromebooks/sync`) so the two stay in step.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_raw_db
from ..schemas.chromebook import TeacherResponse, TeacherUpdate

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


# CTE-based query so each teacher carries their assigned chromebook count plus
# the "primary" chromebook (first one bound) for compact card display.
_LIST_QUERY = """
WITH device_count AS (
    SELECT assigned_teacher_id, COUNT(*) AS cnt
    FROM chromebooks
    WHERE assigned_teacher_id IS NOT NULL
    GROUP BY assigned_teacher_id
),
primary_device AS (
    SELECT assigned_teacher_id,
           MIN(id) AS cb_id
    FROM chromebooks
    WHERE assigned_teacher_id IS NOT NULL
    GROUP BY assigned_teacher_id
)
SELECT t.id, t.google_user_id, t.email, t.full_name, t.given_name,
       t.family_name, t.google_ou_path, t.is_suspended, t.status_local,
       t.arrival_date, t.departure_date, t.notes, t.last_sync,
       t.created_at, t.updated_at,
       COALESCE(dc.cnt, 0) AS chromebook_count,
       pd.cb_id AS primary_cb_id,
       COALESCE(cb.serial_number, '') AS primary_cb_serial,
       COALESCE(cb.model, '') AS primary_cb_model
FROM teachers t
LEFT JOIN device_count dc ON dc.assigned_teacher_id = t.id
LEFT JOIN primary_device pd ON pd.assigned_teacher_id = t.id
LEFT JOIN chromebooks cb ON cb.id = pd.cb_id
"""


def _row_to_teacher(r) -> dict:
    return dict(
        id=r[0],
        google_user_id=r[1] or "",
        email=r[2],
        full_name=r[3] or "",
        given_name=r[4] or "",
        family_name=r[5] or "",
        google_ou_path=r[6] or "",
        is_suspended=bool(r[7]),
        status_local=r[8] or "present",
        arrival_date=r[9],
        departure_date=r[10],
        notes=r[11] or "",
        last_sync=r[12] or "",
        created_at=r[13] or "",
        updated_at=r[14] or "",
        chromebook_count=r[15] or 0,
        primary_chromebook_id=r[16],
        primary_chromebook_serial=r[17] or "",
        primary_chromebook_model=r[18] or "",
    )


@router.get("", response_model=list[TeacherResponse])
async def list_teachers(
    search: str = Query(""),
    status_local: str = Query(""),
    has_device: str = Query(""),  # 'true' / 'false' / ''
    sort: str = Query("name"),  # name / status / recent_sync
    db=Depends(get_raw_db),
):
    where: list[str] = ["1=1"]
    params: list = []

    if search:
        like = f"%{search.lower()}%"
        where.append(
            "(LOWER(t.email) LIKE ? OR LOWER(t.full_name) LIKE ?"
            " OR LOWER(t.given_name) LIKE ? OR LOWER(t.family_name) LIKE ?)"
        )
        params.extend([like, like, like, like])
    if status_local:
        where.append("t.status_local = ?")
        params.append(status_local)
    if has_device == "true":
        where.append("COALESCE(dc.cnt, 0) > 0")
    elif has_device == "false":
        where.append("COALESCE(dc.cnt, 0) = 0")

    order_by = {
        "name": "t.full_name ASC",
        "status": "t.status_local ASC, t.full_name ASC",
        "recent_sync": "t.last_sync DESC",
    }.get(sort, "t.full_name ASC")

    sql = f"{_LIST_QUERY} WHERE {' AND '.join(where)} ORDER BY {order_by}"
    rows = await db.execute_fetchall(sql, params)
    return [TeacherResponse(**_row_to_teacher(r)) for r in rows]


@router.get("/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(teacher_id: int, db=Depends(get_raw_db)):
    sql = f"{_LIST_QUERY} WHERE t.id = ?"
    rows = await db.execute_fetchall(sql, (teacher_id,))
    if not rows:
        raise HTTPException(404, "Prof introuvable")
    return TeacherResponse(**_row_to_teacher(rows[0]))


@router.patch("/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(
    teacher_id: int,
    body: TeacherUpdate,
    db=Depends(get_raw_db),
):
    rows = await db.execute_fetchall(
        "SELECT id FROM teachers WHERE id = ?", (teacher_id,)
    )
    if not rows:
        raise HTTPException(404, "Prof introuvable")

    payload = body.model_dump(exclude_unset=True)
    sets: list[str] = []
    params: list = []
    if "status_local" in payload:
        val = payload["status_local"] or "present"
        if val not in {"present", "partant", "arrivant", "parti"}:
            raise HTTPException(400, "Statut invalide")
        sets.append("status_local = ?")
        params.append(val)
    if "arrival_date" in payload:
        sets.append("arrival_date = ?")
        params.append(payload["arrival_date"] or None)
    if "departure_date" in payload:
        sets.append("departure_date = ?")
        params.append(payload["departure_date"] or None)
    if "notes" in payload:
        sets.append("notes = ?")
        params.append(payload["notes"] or "")

    if not sets:
        # Nothing to change — just return the current row.
        sql = f"{_LIST_QUERY} WHERE t.id = ?"
        rows = await db.execute_fetchall(sql, (teacher_id,))
        return TeacherResponse(**_row_to_teacher(rows[0]))

    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat(timespec="seconds"))
    params.append(teacher_id)
    await db.execute(f"UPDATE teachers SET {', '.join(sets)} WHERE id = ?", params)
    await db.commit()

    sql = f"{_LIST_QUERY} WHERE t.id = ?"
    rows = await db.execute_fetchall(sql, (teacher_id,))
    return TeacherResponse(**_row_to_teacher(rows[0]))


@router.get("/{teacher_id}/chromebooks")
async def teacher_chromebooks(teacher_id: int, db=Depends(get_raw_db)):
    """List all chromebooks currently assigned to this teacher."""
    rows = await db.execute_fetchall(
        """SELECT id, google_device_id, serial_number, model, status_local,
                  binding_source, last_sync
           FROM chromebooks
           WHERE assigned_teacher_id = ?
           ORDER BY model ASC, serial_number ASC""",
        (teacher_id,),
    )
    return [
        {
            "id": r[0], "google_device_id": r[1], "serial_number": r[2],
            "model": r[3], "status_local": r[4], "binding_source": r[5],
            "last_sync": r[6],
        }
        for r in rows
    ]


@router.get("/{teacher_id}/history")
async def teacher_history(teacher_id: int, db=Depends(get_raw_db)):
    """All historic chromebook assignments for this teacher (current + past)."""
    rows = await db.execute_fetchall(
        """SELECT h.id, h.chromebook_id, h.assigned_at, h.returned_at,
                  h.condition_in, h.condition_out, h.notes,
                  COALESCE(c.serial_number,''), COALESCE(c.model,'')
           FROM chromebook_assignments_history h
           LEFT JOIN chromebooks c ON c.id = h.chromebook_id
           WHERE h.teacher_id = ?
           ORDER BY h.assigned_at DESC, h.id DESC""",
        (teacher_id,),
    )
    return [
        {
            "id": r[0], "chromebook_id": r[1],
            "assigned_at": r[2], "returned_at": r[3],
            "condition_in": r[4] or "", "condition_out": r[5] or "",
            "notes": r[6] or "",
            "chromebook_serial": r[7] or "", "chromebook_model": r[8] or "",
        }
        for r in rows
    ]
