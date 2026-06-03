from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ..database import get_raw_db
from ..schemas.supplier import (
    DomainCreate,
    DomainResponse,
    DomainUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)

import os

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])

if os.environ.get("ITMANAGER_DATA_DIR"):
    LOGO_DIR = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data" / "logos"
else:
    LOGO_DIR = Path(__file__).parent.parent / "data" / "logos"
LOGO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def _parse_contacts(s) -> list[dict]:
    """Decode contacts_json, tolerant of null/legacy empty values."""
    if not s:
        return []
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return [
                {
                    "name": str(c.get("name", "")),
                    "role": str(c.get("role", "")),
                    "phone": str(c.get("phone", "")),
                    "email": str(c.get("email", "")),
                }
                for c in data if isinstance(c, dict)
            ]
    except Exception:
        pass
    return []


def _row_to_supplier(r) -> dict:
    return {
        "id": r[0],
        "name": r[1],
        "domain": r[2] or "",
        "phone": r[3] or "",
        "email": r[4] or "",
        "contact": r[5] or "",
        "notes": r[6] or "",
        "logo_path": r[7] or "",
        "created_at": r[8] or "",
        "contacts": _parse_contacts(r[9]) if len(r) > 9 else [],
    }


# ---------------------------------------------------------------------------
# Domain endpoints
# ---------------------------------------------------------------------------

@router.get("/domains", response_model=list[DomainResponse])
async def list_domains(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, name, color_hex, icon_key, sort_order FROM supplier_domains ORDER BY sort_order ASC, name ASC"
    )
    return [
        DomainResponse(id=r[0], name=r[1], color_hex=r[2], icon_key=r[3], sort_order=r[4])
        for r in rows
    ]


@router.post("/domains", response_model=DomainResponse, status_code=201)
async def create_domain(body: DomainCreate, db=Depends(get_raw_db)):
    cursor = await db.execute(
        "INSERT INTO supplier_domains (name, color_hex, icon_key, sort_order) VALUES (?, ?, ?, ?)",
        (body.name, body.color_hex, body.icon_key, body.sort_order),
    )
    await db.commit()
    return DomainResponse(
        id=cursor.lastrowid, name=body.name, color_hex=body.color_hex,
        icon_key=body.icon_key, sort_order=body.sort_order,
    )


@router.put("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(domain_id: int, body: DomainUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM supplier_domains WHERE id = ?", (domain_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.execute(
        "UPDATE supplier_domains SET name=?, color_hex=?, icon_key=?, sort_order=? WHERE id=?",
        (body.name, body.color_hex, body.icon_key, body.sort_order, domain_id),
    )
    await db.commit()
    return DomainResponse(
        id=domain_id, name=body.name, color_hex=body.color_hex,
        icon_key=body.icon_key, sort_order=body.sort_order,
    )


@router.delete("/domains/{domain_id}", status_code=204)
async def delete_domain(domain_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM supplier_domains WHERE id = ?", (domain_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.execute("DELETE FROM supplier_domains WHERE id = ?", (domain_id,))
    await db.commit()


# ---------------------------------------------------------------------------
# Supplier endpoints
# ---------------------------------------------------------------------------

_SUPPLIER_COLS = """id, name, COALESCE(domain,''), COALESCE(phone,''),
                    COALESCE(email,''), COALESCE(contact,''), COALESCE(notes,''),
                    COALESCE(logo_path,''), COALESCE(created_at,''),
                    COALESCE(contacts_json,'[]')"""


def _compute_status_auto(last_interaction: str | None) -> str:
    """Map last_interaction (max doc_date) to a relationship-health bucket.

    Thresholds picked to mirror an IT manager's mental model :
      - within last month        → 'actif_recent'  (just interacted)
      - within last quarter      → 'actif'         (regular contact)
      - within last 6 months     → 'dormant'       (slow but not dead)
      - older OR none            → 'inactif' / 'jamais_utilise'
    """
    if not last_interaction:
        return "jamais_utilise"
    from datetime import date
    # last_interaction is YYYY-MM-DD; tolerate longer strings.
    try:
        y, m, d = (int(x) for x in last_interaction[:10].split("-"))
        delta = (date.today() - date(y, m, d)).days
    except (ValueError, AttributeError):
        return "inactif"
    if delta < 30:
        return "actif_recent"
    if delta < 90:
        return "actif"
    if delta < 180:
        return "dormant"
    return "inactif"


# CTE-based query that joins per-supplier aggregates :
#   - doc_stats : sum of amounts (validated wins) + max(doc_date) per supplier
#   - dossier_stats : counts of total / active dossiers per supplier
#   - supplier_domains : just for the color
# Single query keeps the list endpoint fast even for 50+ suppliers.
_LIST_QUERY = """
WITH doc_stats AS (
    SELECT supplier_id,
           SUM(CASE WHEN amount_accepted > 0 THEN amount_accepted ELSE amount END) AS engaged_total,
           SUM(CASE WHEN substr(COALESCE(doc_date,''), 1, 4) = strftime('%Y', 'now')
                    THEN (CASE WHEN amount_accepted > 0 THEN amount_accepted ELSE amount END)
                    ELSE 0 END) AS engaged_ytd,
           MAX(doc_date) AS last_interaction
    FROM documents
    WHERE supplier_id IS NOT NULL
    GROUP BY supplier_id
),
dossier_stats AS (
    SELECT supplier_id,
           COUNT(*) AS total_dossiers,
           SUM(CASE WHEN status != 'archive' THEN 1 ELSE 0 END) AS active_dossiers
    FROM dossiers
    WHERE supplier_id IS NOT NULL
    GROUP BY supplier_id
)
SELECT s.id, s.name, COALESCE(s.domain,''), COALESCE(s.phone,''),
       COALESCE(s.email,''), COALESCE(s.contact,''), COALESCE(s.notes,''),
       COALESCE(s.logo_path,''), COALESCE(s.created_at,''),
       COALESCE(s.contacts_json,'[]'),
       COALESCE(ds.engaged_total, 0),
       COALESCE(ds.engaged_ytd, 0),
       COALESCE(dc.active_dossiers, 0),
       COALESCE(dc.total_dossiers, 0),
       ds.last_interaction,
       COALESCE(sd.color_hex, '')
FROM suppliers s
LEFT JOIN doc_stats ds ON ds.supplier_id = s.id
LEFT JOIN dossier_stats dc ON dc.supplier_id = s.id
LEFT JOIN supplier_domains sd ON sd.name = s.domain
"""


def _row_to_enriched_supplier(r) -> dict:
    """Build the response dict from a row returned by _LIST_QUERY (16 cols)."""
    base = {
        "id": r[0],
        "name": r[1],
        "domain": r[2] or "",
        "phone": r[3] or "",
        "email": r[4] or "",
        "contact": r[5] or "",
        "notes": r[6] or "",
        "logo_path": r[7] or "",
        "created_at": r[8] or "",
        "contacts": _parse_contacts(r[9]),
    }
    base["engaged_total"] = float(r[10] or 0)
    base["engaged_ytd"] = float(r[11] or 0)
    base["active_dossiers_count"] = int(r[12] or 0)
    base["total_dossiers_count"] = int(r[13] or 0)
    base["last_interaction"] = r[14]
    base["status_auto"] = _compute_status_auto(r[14])
    base["domain_color"] = r[15] or ""
    return base


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    domain: str = Query(""),
    search: str = Query(""),
    status_auto: str = Query("", description="actif_recent | actif | dormant | inactif | jamais_utilise"),
    has_active_dossier: bool = Query(False),
    db=Depends(get_raw_db),
):
    where = " WHERE 1=1"
    params: list = []

    if domain:
        where += " AND s.domain = ?"
        params.append(domain)

    if search:
        where += " AND (s.name LIKE ? OR s.contact LIKE ? OR s.notes LIKE ? OR s.email LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like, like]

    if has_active_dossier:
        where += " AND COALESCE(dc.active_dossiers, 0) > 0"

    order = " ORDER BY s.name COLLATE NOCASE ASC"
    rows = await db.execute_fetchall(_LIST_QUERY + where + order, tuple(params))

    out = [_row_to_enriched_supplier(r) for r in rows]
    # Status filter is applied in Python because it derives from last_interaction
    # via a date computation that we don't want to push into SQL.
    if status_auto:
        out = [s for s in out if s["status_auto"] == status_auto]
    return [SupplierResponse(**s) for s in out]


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: int, db=Depends(get_raw_db)):
    # Single supplier with the same enriched payload as the list endpoint,
    # plus the timeline (recent activity) and the services catalog. v7.1.0.
    rows = await db.execute_fetchall(_LIST_QUERY + " WHERE s.id = ?", (supplier_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Supplier not found")
    data = _row_to_enriched_supplier(rows[0])
    data["timeline"] = await _supplier_timeline(db, supplier_id)
    data["services"] = await _supplier_services(db, supplier_id)
    return SupplierResponse(**data)


async def _supplier_timeline(db, supplier_id: int) -> list[dict]:
    """Recent activity feed for a supplier — last 20 events across all their dossiers.

    Sources merged into a single chronological list :
      - dossier_comments (notes, status changes, deliveries, doc additions)
      - dossier creations (synthetic event at dossiers.created_at)
      - document additions even when no comment was logged (docs that landed
        outside the import flow, e.g. legacy imports pre-v7.0.x)
    """
    events: list[dict] = []

    # 1. Comments / status changes / explicit doc-attached events.
    try:
        rows = await db.execute_fetchall(
            """SELECT dc.kind, dc.body, dc.created_at, d.id, d.title
               FROM dossier_comments dc
               JOIN dossiers d ON d.id = dc.dossier_id
               WHERE d.supplier_id = ?
               ORDER BY datetime(dc.created_at) DESC
               LIMIT 30""",
            (supplier_id,),
        )
        for kind, body, created_at, did, dtitle in rows:
            icon = {
                "status": "↻",
                "doc": "📄",
                "note": "💬",
                "delivery": "📦",
                "system": "⚙",
            }.get(kind, "•")
            events.append({
                "kind": kind, "body": body or "", "created_at": created_at,
                "dossier_id": did, "dossier_title": dtitle, "icon": icon,
            })
    except Exception:
        pass

    # 2. Synthetic "dossier created" events.
    try:
        rows = await db.execute_fetchall(
            "SELECT id, title, created_at FROM dossiers WHERE supplier_id = ? ORDER BY datetime(created_at) DESC LIMIT 20",
            (supplier_id,),
        )
        for did, dtitle, created_at in rows:
            events.append({
                "kind": "dossier_created",
                "body": f"Dossier ouvert : {dtitle}",
                "created_at": created_at,
                "dossier_id": did, "dossier_title": dtitle, "icon": "🗂",
            })
    except Exception:
        pass

    # Sort descending by created_at and trim to 20.
    events.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return events[:20]


async def _supplier_services(db, supplier_id: int) -> list[dict]:
    """Catalog auto-deduced from the doc types the user has had with this supplier.
    Returns a list sorted by descending count, e.g. [{doc_type:'FACTURE', count:8}, …]."""
    try:
        rows = await db.execute_fetchall(
            """SELECT UPPER(COALESCE(doc_type,'AUTRE')) AS dt, COUNT(*) AS n
               FROM documents
               WHERE supplier_id = ?
               GROUP BY dt
               ORDER BY n DESC""",
            (supplier_id,),
        )
        return [{"doc_type": r[0], "count": r[1]} for r in rows]
    except Exception:
        return []


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(body: SupplierCreate, db=Depends(get_raw_db)):
    now = datetime.now().isoformat(timespec="seconds")
    contacts_json = json.dumps([c.model_dump() for c in body.contacts])
    try:
        cursor = await db.execute(
            """INSERT INTO suppliers (name, domain, phone, email, contact, notes, logo_path, created_at, contacts_json)
               VALUES (?, ?, ?, ?, ?, ?, '', ?, ?)""",
            (body.name, body.domain, body.phone, body.email, body.contact, body.notes, now, contacts_json),
        )
    except Exception:
        # Fallback if contacts_json column doesn't exist yet
        cursor = await db.execute(
            """INSERT INTO suppliers (name, domain, phone, email, contact, notes, logo_path, created_at)
               VALUES (?, ?, ?, ?, ?, ?, '', ?)""",
            (body.name, body.domain, body.phone, body.email, body.contact, body.notes, now),
        )
    await db.commit()
    supplier_id = cursor.lastrowid
    rows = await db.execute_fetchall(
        f"SELECT {_SUPPLIER_COLS} FROM suppliers WHERE id = ?",
        (supplier_id,),
    )
    return SupplierResponse(**_row_to_supplier(rows[0]))


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(supplier_id: int, body: SupplierUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM suppliers WHERE id = ?", (supplier_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Supplier not found")

    contacts_json = json.dumps([c.model_dump() for c in body.contacts])
    try:
        await db.execute(
            """UPDATE suppliers SET name=?, domain=?, phone=?, email=?, contact=?, notes=?, contacts_json=?
               WHERE id=?""",
            (body.name, body.domain, body.phone, body.email, body.contact, body.notes, contacts_json, supplier_id),
        )
    except Exception:
        await db.execute(
            """UPDATE suppliers SET name=?, domain=?, phone=?, email=?, contact=?, notes=?
               WHERE id=?""",
            (body.name, body.domain, body.phone, body.email, body.contact, body.notes, supplier_id),
        )
    await db.commit()
    return await get_supplier(supplier_id, db)


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(supplier_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM suppliers WHERE id = ?", (supplier_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Remove logo file if it exists
    logo_rows = await db.execute_fetchall(
        "SELECT logo_path FROM suppliers WHERE id = ?", (supplier_id,),
    )
    if logo_rows and logo_rows[0][0]:
        logo_file = LOGO_DIR / logo_rows[0][0]
        if logo_file.exists():
            logo_file.unlink()

    await db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    await db.commit()


# ---------------------------------------------------------------------------
# Logo endpoints
# ---------------------------------------------------------------------------

@router.post("/{supplier_id}/logo", response_model=SupplierResponse)
async def upload_logo(supplier_id: int, file: UploadFile = File(...), db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT logo_path FROM suppliers WHERE id = ?", (supplier_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Supplier not found")

    ext = Path(file.filename or "upload.png").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

    content = await file.read()
    hash8 = hashlib.md5(content).hexdigest()[:8]
    filename = f"{supplier_id}_{hash8}{ext}"

    # Remove old logo if present
    old_path = rows[0][0]
    if old_path:
        old_file = LOGO_DIR / old_path
        if old_file.exists():
            old_file.unlink()

    (LOGO_DIR / filename).write_bytes(content)

    await db.execute(
        "UPDATE suppliers SET logo_path = ? WHERE id = ?",
        (filename, supplier_id),
    )
    await db.commit()
    return await get_supplier(supplier_id, db)


@router.get("/{supplier_id}/logo")
async def serve_logo(supplier_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT logo_path FROM suppliers WHERE id = ?", (supplier_id,),
    )
    if not rows or not rows[0][0]:
        raise HTTPException(status_code=404, detail="Logo not found")

    logo_path = LOGO_DIR / rows[0][0]
    if not logo_path.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")

    ext = logo_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return Response(
        content=logo_path.read_bytes(),
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )
