"""Dossiers — top-level procurement workflow unit (v7.0.0).

A dossier groups all documents (Devis, BPA, Facture, …) related to one
procurement case (e.g. "Renouvellement firewall NDK"). It carries the
high-level state of that case, plus an activity feed (notes, status
changes, deliveries).

Endpoints:
  GET    /api/dossiers                       list with filters
  GET    /api/dossiers/{id}                  detail (incl. docs + comments)
  GET    /api/dossiers/stats/summary         counts by status / smart filters
  POST   /api/dossiers                       create
  PUT    /api/dossiers/{id}                  update fields
  DELETE /api/dossiers/{id}                  delete (docs detached, not lost)
  POST   /api/dossiers/{id}/attach           attach an existing document
  DELETE /api/dossiers/{id}/documents/{did}  detach a document
  POST   /api/dossiers/{id}/comments         add a comment / note
  PUT    /api/dossiers/{id}/status           change status (logs to comments)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..database import get_raw_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dossiers", tags=["dossiers"])


# ── Constants ──────────────────────────────────────────────

VALID_STATUSES = {
    "demande_envoyee",
    "devis_recu",
    "bpa_signe",
    "commande",
    "livre",
    "archive",
}

# Status hierarchy — used to order/colorize. Lower = earlier in lifecycle.
STATUS_RANK = {
    "demande_envoyee": 0,
    "devis_recu": 1,
    "bpa_signe": 2,
    "commande": 3,
    "livre": 4,
    "archive": 5,
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalise_status(s: str | None) -> str:
    return s if s in VALID_STATUSES else "demande_envoyee"


# ── Pydantic models ────────────────────────────────────────

class DossierCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "demande_envoyee"
    supplier_id: int | None = None
    project_id: int | None = None
    site: str = ""
    estimated_budget: float = 0
    notes: str = ""
    next_action_date: str | None = None
    next_action_label: str = ""


class DossierUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    supplier_id: int | None = None
    project_id: int | None = None
    site: str | None = None
    estimated_budget: float | None = None
    notes: str | None = None
    next_action_date: str | None = None
    next_action_label: str | None = None
    received_at: str | None = None
    archived_at: str | None = None


class CommentCreate(BaseModel):
    body: str
    kind: str = "note"  # 'note' | 'delivery' | 'system'


class StatusChange(BaseModel):
    status: str
    note: str = ""


# ── Helpers ────────────────────────────────────────────────

async def _doc_summary_for_dossier(db, dossier_id: int) -> dict:
    """Aggregate per-dossier doc stats (amounts, counts, types).

    v7.0.1: reads amounts straight from `documents.amount` / `amount_accepted`
    (so docs without a project link still contribute). The old join-on-
    project_documents path is gone; the data has been backfilled by the
    migration in database.py.

    Returns: { 'doc_count', 'chain_types', 'devis_total',
               'bpa_total', 'facture_total', 'has_acompte' }
    """
    rows = await db.execute_fetchall(
        """SELECT id, COALESCE(doc_type,''), COALESCE(is_acompte, 0),
                  COALESCE(amount, 0), COALESCE(amount_accepted, 0)
           FROM documents
           WHERE dossier_id = ?""",
        (dossier_id,),
    )
    chain_types: set[str] = set()
    devis_total = 0.0
    bpa_total = 0.0
    facture_total = 0.0
    has_acompte = False

    for r in rows:
        dtype = (r[1] or "").upper()
        is_acompte = bool(r[2])
        amount = r[3] or 0
        accepted = r[4] or 0
        # "Validated" amount wins when set, else fall back to the declared one.
        value = accepted if accepted > 0 else amount

        if dtype:
            chain_types.add(dtype)
        if is_acompte and dtype == "FACTURE":
            has_acompte = True
        if dtype == "DEVIS":
            devis_total += value
        elif dtype in ("BPA", "BON"):
            bpa_total += value
        elif dtype == "FACTURE":
            facture_total += value

    return {
        "doc_count": len(rows),
        "chain_types": sorted(chain_types),
        "devis_total": devis_total,
        "bpa_total": bpa_total,
        "facture_total": facture_total,
        "has_acompte": has_acompte,
    }


async def _supplier_brief(db, supplier_id: int | None) -> dict | None:
    """Return a small dict describing a supplier (id, name, color, has_logo).

    The suppliers table has no `color` column — color comes from the
    supplier_domains table joined on suppliers.domain. Fixed in v7.0.5
    (previously this query referenced suppliers.color and silently failed
    with a SQLite error, leaving every dossier supplier-less in the UI even
    when `dossiers.supplier_id` was set correctly in DB).
    """
    if not supplier_id:
        return None
    try:
        rows = await db.execute_fetchall(
            """SELECT s.id, s.name,
                      COALESCE(sd.color_hex, '#6C63FF') AS color,
                      COALESCE(s.logo_path, '') AS logo_path
               FROM suppliers s
               LEFT JOIN supplier_domains sd ON sd.name = s.domain
               WHERE s.id = ?""",
            (supplier_id,),
        )
        if not rows:
            return None
        r = rows[0]
        return {"id": r[0], "name": r[1], "color": r[2], "has_logo": bool(r[3])}
    except Exception as e:
        logger.warning(f"_supplier_brief({supplier_id}) failed: {e}")
        return None


async def _project_brief(db, project_id: int | None) -> dict | None:
    if not project_id:
        return None
    try:
        rows = await db.execute_fetchall(
            "SELECT id, title, COALESCE(color, '#3B82F6'), COALESCE(status,'') FROM projects WHERE id = ?",
            (project_id,),
        )
        if not rows:
            return None
        r = rows[0]
        return {"id": r[0], "title": r[1], "color": r[2], "status": r[3]}
    except Exception:
        return None


async def _row_to_dossier(db, r) -> dict:
    summary = await _doc_summary_for_dossier(db, r[0])
    supplier = await _supplier_brief(db, r[3])
    project = await _project_brief(db, r[4])
    return {
        "id": r[0],
        "title": r[1] or "",
        "description": r[2] or "",
        "status": r[3] if isinstance(r[3], str) else "",  # placeholder; actual status pulled below
        # NOTE: column order depends on SELECT, so use named pulls below where useful
    }


# ── List + stats ───────────────────────────────────────────

_BASE_SELECT = (
    # v7.0.10 — left-join a CTE that aggregates the doc dates per dossier.
    # `first_doc_date` and `last_doc_date` carry the earliest and most-recent
    # `doc_date` (= the date written on the supplier's PDF) — used by the UI
    # to display "Dernière activité" on each card, sort, and filter by period.
    "WITH doc_dates AS ("
    "  SELECT dossier_id,"
    "         MIN(doc_date) AS first_doc_date,"
    "         MAX(doc_date) AS last_doc_date"
    "  FROM documents"
    "  WHERE dossier_id IS NOT NULL AND doc_date IS NOT NULL AND doc_date != ''"
    "  GROUP BY dossier_id"
    ")"
    "SELECT d.id, d.title, COALESCE(d.description,''), COALESCE(d.status,'demande_envoyee'), "
    "d.supplier_id, d.project_id, COALESCE(d.site,''), COALESCE(d.estimated_budget,0), "
    "d.received_at, d.archived_at, d.next_action_date, COALESCE(d.next_action_label,''), "
    "COALESCE(d.notes,''), d.created_at, d.updated_at, "
    "dd.first_doc_date, dd.last_doc_date "
    "FROM dossiers d "
    "LEFT JOIN doc_dates dd ON dd.dossier_id = d.id"
)


def _row_to_dict(r) -> dict:
    return {
        "id": r[0],
        "title": r[1],
        "description": r[2],
        "status": r[3],
        "supplier_id": r[4],
        "project_id": r[5],
        "site": r[6],
        "estimated_budget": r[7],
        "received_at": r[8],
        "archived_at": r[9],
        "next_action_date": r[10],
        "next_action_label": r[11],
        "notes": r[12],
        "created_at": r[13],
        "updated_at": r[14],
        "first_doc_date": r[15],
        "last_doc_date": r[16],
    }


@router.get("")
async def list_dossiers(
    status: str = Query("", description="Filter by status (single value or empty)"),
    supplier_id: int | None = Query(None),
    project_id: int | None = Query(None),
    site: str = Query(""),
    search: str = Query(""),
    sort: str = Query("recent", description="recent | recent_doc | oldest_doc | title"),
    period: str = Query("all", description="all | 30d | 90d | this_year | YYYY (4-digit year)"),
    db=Depends(get_raw_db),
):
    # All column refs use the `d.` alias because the _BASE_SELECT is now
    # a JOIN'd query (CTE + dossiers d).
    where = " WHERE 1=1"
    params: list = []
    if status:
        where += " AND d.status = ?"
        params.append(status)
    if supplier_id is not None:
        where += " AND d.supplier_id = ?"
        params.append(supplier_id)
    if project_id is not None:
        where += " AND d.project_id = ?"
        params.append(project_id)
    if site:
        where += " AND d.site = ?"
        params.append(site)
    if search:
        # v7.0.8 — also match dossiers whose attached documents contain the
        # query in their title or internal_ref. So searching "Konica" finds
        # not only dossiers named "Konica…" but also dossiers that have a
        # facture titled "Facture Konica - …" inside.
        where += """ AND (
            d.title LIKE ? OR d.description LIKE ? OR d.notes LIKE ?
            OR d.id IN (
                SELECT dossier_id FROM documents
                WHERE dossier_id IS NOT NULL
                AND (title LIKE ? OR COALESCE(reference,'') LIKE ? OR COALESCE(internal_ref,'') LIKE ?)
            )
        )"""
        like = f"%{search}%"
        params += [like, like, like, like, like, like]

    # Period filter — operates on the dossier's last_doc_date (the
    # most-recent paper date among its attachments). Dossiers without any
    # dated doc are excluded when a specific period is requested.
    if period and period != "all":
        from datetime import date, timedelta
        today = date.today()
        if period == "30d":
            cutoff = (today - timedelta(days=30)).isoformat()
            where += " AND dd.last_doc_date >= ?"
            params.append(cutoff)
        elif period == "90d":
            cutoff = (today - timedelta(days=90)).isoformat()
            where += " AND dd.last_doc_date >= ?"
            params.append(cutoff)
        elif period == "this_year":
            where += " AND substr(dd.last_doc_date, 1, 4) = ?"
            params.append(str(today.year))
        elif period.isdigit() and len(period) == 4:
            # explicit year filter, e.g. "2024"
            where += " AND substr(dd.last_doc_date, 1, 4) = ?"
            params.append(period)

    # Sort. Archived dossiers always at the bottom regardless of sort.
    sort_clauses = {
        "recent": "ORDER BY CASE d.status WHEN 'archive' THEN 1 ELSE 0 END, datetime(d.updated_at) DESC",
        "recent_doc": "ORDER BY CASE d.status WHEN 'archive' THEN 1 ELSE 0 END, CASE WHEN dd.last_doc_date IS NULL THEN 1 ELSE 0 END, dd.last_doc_date DESC",
        "oldest_doc": "ORDER BY CASE d.status WHEN 'archive' THEN 1 ELSE 0 END, CASE WHEN dd.first_doc_date IS NULL THEN 1 ELSE 0 END, dd.first_doc_date ASC",
        "title": "ORDER BY CASE d.status WHEN 'archive' THEN 1 ELSE 0 END, d.title COLLATE NOCASE ASC",
    }
    order = " " + sort_clauses.get(sort, sort_clauses["recent"])
    rows = await db.execute_fetchall(_BASE_SELECT + where + order, tuple(params))

    out = []
    for r in rows:
        d = _row_to_dict(r)
        d["supplier"] = await _supplier_brief(db, d["supplier_id"])
        d["project"] = await _project_brief(db, d["project_id"])
        d["summary"] = await _doc_summary_for_dossier(db, d["id"])
        out.append(d)
    return out


@router.get("/stats/summary")
async def stats_summary(db=Depends(get_raw_db)):
    """Counts per status + a few smart-filter buckets for sidebar badges."""
    try:
        rows = await db.execute_fetchall(
            "SELECT status, COUNT(*) FROM dossiers GROUP BY status"
        )
        per_status = {r[0]: r[1] for r in rows}
        total = sum(per_status.values())

        # Smart-filter counts.
        today = datetime.now().date().isoformat()
        relance_rows = await db.execute_fetchall(
            "SELECT COUNT(*) FROM dossiers "
            "WHERE next_action_date IS NOT NULL AND next_action_date <= ? "
            "AND status NOT IN ('livre','archive')",
            (today,),
        )
        a_relancer = relance_rows[0][0] if relance_rows else 0

        livraison_rows = await db.execute_fetchall(
            "SELECT COUNT(*) FROM dossiers WHERE status = 'commande'"
        )
        livraison_attendue = livraison_rows[0][0] if livraison_rows else 0

        return {
            "total": total,
            "per_status": per_status,
            "smart": {
                "a_relancer": a_relancer,
                "livraison_attendue": livraison_attendue,
            },
        }
    except Exception as e:
        logger.warning(f"dossier stats failed: {e}")
        return {"total": 0, "per_status": {}, "smart": {}}


# ── Detail ─────────────────────────────────────────────────

@router.get("/{dossier_id}")
async def get_dossier(dossier_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        _BASE_SELECT + " WHERE d.id = ?", (dossier_id,)
    )
    if not rows:
        raise HTTPException(404, "Dossier introuvable")
    d = _row_to_dict(rows[0])
    d["supplier"] = await _supplier_brief(db, d["supplier_id"])
    d["project"] = await _project_brief(db, d["project_id"])
    d["summary"] = await _doc_summary_for_dossier(db, d["id"])

    # Docs in this dossier (amounts read from document row directly — v7.0.1).
    doc_rows = await db.execute_fetchall(
        """SELECT id, title, COALESCE(doc_type,''), doc_date,
                  COALESCE(reference,''), COALESCE(internal_ref,''),
                  COALESCE(is_acompte, 0),
                  COALESCE(amount, 0), COALESCE(amount_accepted, 0)
           FROM documents
           WHERE dossier_id = ?
           ORDER BY
             CASE COALESCE(doc_type,'')
               WHEN 'DEVIS' THEN 1
               WHEN 'PROPOSITION' THEN 2
               WHEN 'BPA' THEN 3
               WHEN 'BON' THEN 3
               WHEN 'CONTRAT' THEN 4
               WHEN 'FACTURE' THEN 5
               WHEN 'RAPPORT' THEN 6
               ELSE 7
             END,
             COALESCE(doc_date, created_at) ASC""",
        (dossier_id,),
    )
    d["documents"] = [
        {
            "id": r[0],
            "title": r[1],
            "doc_type": r[2],
            "doc_date": r[3],
            "reference": r[4],
            "internal_ref": r[5],
            "is_acompte": bool(r[6]),
            "amount": r[7],
            "amount_accepted": r[8],
        }
        for r in doc_rows
    ]

    # Comments / activity feed.
    try:
        c_rows = await db.execute_fetchall(
            "SELECT id, kind, body, COALESCE(meta,'{}'), created_at FROM dossier_comments "
            "WHERE dossier_id = ? ORDER BY datetime(created_at) DESC",
            (dossier_id,),
        )
        d["comments"] = [
            {
                "id": r[0],
                "kind": r[1],
                "body": r[2],
                "meta": _json_safe(r[3]),
                "created_at": r[4],
            }
            for r in c_rows
        ]
    except Exception:
        d["comments"] = []
    return d


def _json_safe(s: str) -> dict:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


# ── Mutations ──────────────────────────────────────────────

@router.post("", status_code=201)
async def create_dossier(body: DossierCreate, db=Depends(get_raw_db)):
    status = _normalise_status(body.status)
    now = _now()
    cursor = await db.execute(
        """INSERT INTO dossiers
           (title, description, status, supplier_id, project_id, site, estimated_budget,
            notes, next_action_date, next_action_label, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            body.title.strip() or "Nouveau dossier",
            body.description, status, body.supplier_id, body.project_id, body.site,
            body.estimated_budget, body.notes, body.next_action_date,
            body.next_action_label, now, now,
        ),
    )
    await db.commit()
    return await get_dossier(cursor.lastrowid, db)


@router.put("/{dossier_id}")
async def update_dossier(dossier_id: int, body: DossierUpdate, db=Depends(get_raw_db)):
    # v7.0.4 — log every PUT payload so we can diagnose missing fields when
    # the frontend / Pydantic stack drop something silently.
    logger.info(
        "[update_dossier] id=%s body=%s",
        dossier_id, body.model_dump(),
    )

    existing = await db.execute_fetchall(
        "SELECT status FROM dossiers WHERE id = ?", (dossier_id,)
    )
    if not existing:
        raise HTTPException(404, "Dossier introuvable")
    old_status = existing[0][0]

    fields: list[str] = []
    params: list = []
    payload = body.model_dump(exclude_unset=True)
    logger.info(
        "[update_dossier] id=%s payload(exclude_unset)=%s",
        dossier_id, payload,
    )
    if "status" in payload:
        payload["status"] = _normalise_status(payload["status"])
    for k in (
        "title", "description", "status", "supplier_id", "project_id", "site",
        "estimated_budget", "notes", "next_action_date", "next_action_label",
        "received_at", "archived_at",
    ):
        if k in payload:
            fields.append(f"{k} = ?")
            params.append(payload[k])
    if not fields:
        return await get_dossier(dossier_id, db)

    fields.append("updated_at = ?")
    params.append(_now())
    params.append(dossier_id)

    await db.execute(
        f"UPDATE dossiers SET {', '.join(fields)} WHERE id = ?",
        tuple(params),
    )

    # Log status changes to the activity feed so the user can see the history.
    if "status" in payload and payload["status"] != old_status:
        await db.execute(
            "INSERT INTO dossier_comments (dossier_id, kind, body, meta, created_at) "
            "VALUES (?, 'status', ?, ?, ?)",
            (dossier_id, f"Statut : {old_status} → {payload['status']}",
             json.dumps({"from": old_status, "to": payload["status"]}), _now()),
        )

    await db.commit()
    return await get_dossier(dossier_id, db)


@router.delete("/{dossier_id}", status_code=204)
async def delete_dossier(dossier_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
    if not rows:
        raise HTTPException(404, "Dossier introuvable")

    # Detach docs (they survive — the user might want to re-attach them elsewhere).
    await db.execute("UPDATE documents SET dossier_id = NULL WHERE dossier_id = ?", (dossier_id,))
    # ON DELETE CASCADE cleans up the comments.
    await db.execute("DELETE FROM dossiers WHERE id = ?", (dossier_id,))
    await db.commit()


@router.post("/{dossier_id}/attach")
async def attach_document(dossier_id: int, body: dict, db=Depends(get_raw_db)):
    doc_id = body.get("document_id")
    if not doc_id:
        raise HTTPException(400, "document_id requis")

    dossier_rows = await db.execute_fetchall("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
    if not dossier_rows:
        raise HTTPException(404, "Dossier introuvable")

    doc_rows = await db.execute_fetchall(
        "SELECT id, title, COALESCE(doc_type,'') FROM documents WHERE id = ?", (doc_id,)
    )
    if not doc_rows:
        raise HTTPException(404, "Document introuvable")

    await db.execute(
        "UPDATE documents SET dossier_id = ? WHERE id = ?",
        (dossier_id, doc_id),
    )
    # Log to activity feed.
    await db.execute(
        "INSERT INTO dossier_comments (dossier_id, kind, body, meta, created_at) "
        "VALUES (?, 'doc', ?, ?, ?)",
        (
            dossier_id,
            f"Document ajouté au dossier : {doc_rows[0][1]} ({doc_rows[0][2] or 'autre'})",
            json.dumps({"document_id": doc_id, "doc_type": doc_rows[0][2]}),
            _now(),
        ),
    )
    # Bump dossier updated_at so it surfaces in recent activity.
    await db.execute(
        "UPDATE dossiers SET updated_at = ? WHERE id = ?", (_now(), dossier_id)
    )
    await db.commit()
    return await get_dossier(dossier_id, db)


@router.delete("/{dossier_id}/documents/{doc_id}", status_code=204)
async def detach_document(dossier_id: int, doc_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM documents WHERE id = ? AND dossier_id = ?", (doc_id, dossier_id)
    )
    if not rows:
        raise HTTPException(404, "Document non lié à ce dossier")
    await db.execute(
        "UPDATE documents SET dossier_id = NULL WHERE id = ? AND dossier_id = ?",
        (doc_id, dossier_id),
    )
    await db.execute(
        "UPDATE dossiers SET updated_at = ? WHERE id = ?", (_now(), dossier_id)
    )
    await db.commit()


@router.post("/{dossier_id}/comments", status_code=201)
async def add_comment(dossier_id: int, body: CommentCreate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM dossiers WHERE id = ?", (dossier_id,))
    if not rows:
        raise HTTPException(404, "Dossier introuvable")
    cursor = await db.execute(
        "INSERT INTO dossier_comments (dossier_id, kind, body, meta, created_at) "
        "VALUES (?, ?, ?, '{}', ?)",
        (dossier_id, body.kind or "note", body.body, _now()),
    )
    await db.execute(
        "UPDATE dossiers SET updated_at = ? WHERE id = ?", (_now(), dossier_id)
    )
    await db.commit()
    return {"id": cursor.lastrowid}


@router.put("/{dossier_id}/status")
async def change_status(dossier_id: int, body: StatusChange, db=Depends(get_raw_db)):
    """Shortcut endpoint for the status pill on a card — applies the new
    status and optionally an attached note in one transaction."""
    new_status = _normalise_status(body.status)
    rows = await db.execute_fetchall(
        "SELECT status FROM dossiers WHERE id = ?", (dossier_id,)
    )
    if not rows:
        raise HTTPException(404, "Dossier introuvable")
    old_status = rows[0][0]
    now = _now()

    extras: list[str] = []
    params: list = [new_status, now]

    # Cohort: when moving INTO 'livre', stamp received_at if not set yet.
    if new_status == "livre":
        extras.append("received_at = COALESCE(received_at, ?)")
        params.insert(1, now)
    if new_status == "archive":
        extras.append("archived_at = COALESCE(archived_at, ?)")
        params.insert(1, now)

    set_clause = "status = ?, updated_at = ?" + ("".join(", " + e for e in extras))
    # Re-order params for the actual SQL: status, updated_at, [extras…], id
    # The extras above were inserted before updated_at; rebuild cleanly:
    sql_params: list = [new_status]
    if new_status == "livre":
        sql_params.append(now)  # received_at
    if new_status == "archive":
        sql_params.append(now)  # archived_at
    sql_params.append(now)  # updated_at
    sql_params.append(dossier_id)

    set_parts = ["status = ?"]
    if new_status == "livre":
        set_parts.append("received_at = COALESCE(received_at, ?)")
    if new_status == "archive":
        set_parts.append("archived_at = COALESCE(archived_at, ?)")
    set_parts.append("updated_at = ?")
    await db.execute(
        f"UPDATE dossiers SET {', '.join(set_parts)} WHERE id = ?",
        tuple(sql_params),
    )

    # Activity log.
    note_body = f"Statut : {old_status} → {new_status}"
    if body.note:
        note_body += f"\n{body.note}"
    await db.execute(
        "INSERT INTO dossier_comments (dossier_id, kind, body, meta, created_at) "
        "VALUES (?, 'status', ?, ?, ?)",
        (dossier_id, note_body,
         json.dumps({"from": old_status, "to": new_status}), now),
    )
    await db.commit()
    return await get_dossier(dossier_id, db)
