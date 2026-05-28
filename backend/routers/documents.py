from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

import os

from ..database import get_raw_db

if os.environ.get("ITMANAGER_DATA_DIR"):
    VAULT_ROOT = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data" / "documents"
else:
    VAULT_ROOT = Path(__file__).parent.parent / "data" / "documents"
VAULT_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
               ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
               ".txt", ".csv", ".zip", ".rar", ".7z"}

MIME_MAP = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".bmp": "image/bmp",
    ".svg": "image/svg+xml", ".webp": "image/webp",
    ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain", ".csv": "text/csv",
}
from ..schemas.document import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentLinkCreate,
    DocumentLinkResponse,
    DocumentResponse,
    DocumentUpdate,
    TagResponse,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _row_to_document(r) -> dict:
    rel_path = r[7] or ""
    # v7.0.7 — flag rows whose underlying PDF was deleted on disk. The
    # frontend uses this to hide stale orphan rows in the "Rattacher un
    # document" picker. The check is a cheap fs stat; for 1000+ docs we'd
    # need to cache but at this scale it's fine.
    file_missing = bool(rel_path) and not (VAULT_ROOT / rel_path).exists()
    return {
        "id": r[0],
        "title": r[1],
        "doc_type": r[2] or "",
        "supplier_id": r[3],
        "supplier_name": r[4] or "",
        "doc_date": r[5],
        "reference": r[6] or "",
        "file_path": rel_path,
        "file_hash": r[8] or "",
        "notes": r[9] or "",
        "created_at": r[10] or "",
        # Optional CSV of tag names (present on list endpoint, empty otherwise)
        "tags": r[11] if len(r) > 11 and r[11] else "",
        "internal_ref": r[12] if len(r) > 12 and r[12] else "",
        "is_acompte": bool(r[13]) if len(r) > 13 else False,
        "file_missing": file_missing,
    }


# Type prefix map for internal references — DEV-2026-001 etc.
_TYPE_PREFIX = {
    "DEVIS": "DEV", "FACTURE": "FAC", "BPA": "BPA", "BON": "BPA",
    "CONTRAT": "CTR", "RAPPORT": "RAP", "AUTRE": "AUT",
}


async def _next_internal_ref(db, doc_type: str, year_str: str) -> str:
    """Compute the next internal reference for a (type, year) pair.
    Returns e.g. 'DEV-2026-007'. Caller must run inside a transaction.
    """
    prefix = _TYPE_PREFIX.get((doc_type or "AUTRE").upper(), "AUT")
    if not (year_str and year_str.isdigit() and len(year_str) == 4):
        year_str = str(datetime.now().year)
    pattern = f"{prefix}-{year_str}-%"
    rows = await db.execute_fetchall(
        "SELECT internal_ref FROM documents WHERE internal_ref LIKE ?",
        (pattern,),
    )
    max_seq = 0
    for row in rows:
        ref = row[0] or ""
        # ref looks like DEV-2026-042 → take the last segment
        try:
            n = int(ref.rsplit("-", 1)[-1])
            if n > max_seq:
                max_seq = n
        except Exception:
            pass
    return f"{prefix}-{year_str}-{(max_seq + 1):03d}"


@router.get("/types")
async def list_doc_types(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT DISTINCT doc_type FROM documents WHERE doc_type IS NOT NULL AND doc_type != '' ORDER BY doc_type ASC"
    )
    return [r[0] for r in rows]


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, name, COALESCE(created_at,'') FROM tags ORDER BY name ASC"
    )
    return [TagResponse(id=r[0], name=r[1], created_at=r[2]) for r in rows]


# ── Document Links (static prefix must come BEFORE /{doc_id}) ──


@router.get("/links-graph")
async def list_all_document_links(db=Depends(get_raw_db)):
    """All document_links rows in one shot, used by the UI to group connected
    documents into workflow cards (Devis → BPA → Facture etc.). Cheaper than
    one-call-per-doc and stable enough to fetch alongside the list."""
    rows = await db.execute_fetchall(
        "SELECT source_id, target_id, COALESCE(link_type, '') FROM document_links"
    )
    return [{"source_id": r[0], "target_id": r[1], "link_type": r[2]} for r in rows]


@router.delete("/links/{link_id}", status_code=204)
async def delete_document_link(link_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM document_links WHERE id = ?", (link_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.execute("DELETE FROM document_links WHERE id = ?", (link_id,))
    await db.commit()


# ── File upload helpers ─────────────────────────────────────────

def _detect_doc_type(filename: str) -> str:
    """Auto-detect document type from filename patterns."""
    name = filename.upper()
    if re.search(r"DEVIS|QUOTE|QUOTATION|PROFORMA", name):
        return "DEVIS"
    if re.search(r"FACTURE|INVOICE|FACT[_\-]", name):
        return "FACTURE"
    if re.search(r"CONTRAT|CONTRACT|AGREEMENT", name):
        return "CONTRAT"
    if re.search(r"BON|BPA|BC[_\-]|ORDER", name):
        return "BON"
    if re.search(r"RAPPORT|REPORT|CR[_\-]|COMPTE[_\-]?RENDU", name):
        return "RAPPORT"
    return ""


def _detect_date(filename: str) -> str:
    """Try to extract a date from filename (multiple formats)."""
    # 2024-01-15 or 2024_01_15
    m = re.search(r"(20\d{2})[\-_](0[1-9]|1[0-2])[\-_](0[1-9]|[12]\d|3[01])", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # 15-01-2024 or 15_01_2024
    m = re.search(r"(0[1-9]|[12]\d|3[01])[\-_](0[1-9]|1[0-2])[\-_](20\d{2})", filename)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # 20240115
    m = re.search(r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def _sanitize_filename(name: str) -> str:
    """Remove dangerous characters from a filename."""
    name = Path(name).name  # strip any directory components
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name.strip() or "document"


async def _store_file(file: UploadFile, doc_type: str) -> tuple[str, str]:
    """Copy uploaded file into vault, return (relative_path, sha256)."""
    content = await file.read()
    sha = hashlib.sha256(content).hexdigest()

    ext = Path(file.filename or "file").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Extension {ext} non autorisée")

    year = str(datetime.now().year)
    dtype_folder = (doc_type or "AUTRE").upper()
    safe_name = _sanitize_filename(file.filename or "document" + ext)

    dest_dir = VAULT_ROOT / year / dtype_folder
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / safe_name
    # Handle duplicates: add hash prefix
    if dest.exists():
        stem = dest.stem
        dest = dest_dir / f"{stem}_{sha[:8]}{ext}"

    dest.write_bytes(content)
    # Store relative path from VAULT_ROOT
    rel_path = str(dest.relative_to(VAULT_ROOT)).replace("\\", "/")
    return rel_path, sha


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    doc_type: str = Form(""),
    supplier: str = Form(""),
    supplier_id: int | None = Form(None),  # v7.0.8 — take precedence over the name (deterministic lookup)
    doc_date: str = Form(""),
    reference: str = Form(""),
    notes: str = Form(""),
    tags: str = Form(""),
    is_acompte: int = Form(0),
    link_to_id: int | None = Form(None),
    db=Depends(get_raw_db),
):
    """Upload a single file and create a document record."""
    filename = file.filename or "document"

    # Auto-detect metadata from filename if not provided
    if not doc_type:
        doc_type = _detect_doc_type(filename)
    if not doc_date:
        doc_date = _detect_date(filename)
    if not title:
        title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()

    rel_path, sha = await _store_file(file, doc_type)

    # Check for duplicate by SHA256. Two scenarios :
    #   1. The existing row is an orphan (its file_path doesn't exist on disk) —
    #      typically left over from a previous upload + manual delete from disk.
    #      We silently clean it up and let the new upload proceed.
    #   2. The existing row's file IS still on disk — real duplicate. Throw a
    #      helpful 409 pointing to the existing document so the user knows to
    #      rattacher au lieu de re-importer.
    existing = await db.execute_fetchall(
        "SELECT id, title, COALESCE(file_path,'') FROM documents WHERE file_hash = ?", (sha,)
    )
    if existing:
        existing_id, existing_title, existing_path = existing[0]
        existing_alive = bool(existing_path) and (VAULT_ROOT / existing_path).exists()
        if existing_alive:
            # Real duplicate — drop the freshly stored copy so we don't leak files,
            # and tell the user where the original is.
            try:
                (VAULT_ROOT / rel_path).unlink()
            except OSError:
                pass
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Un document avec ce contenu existe déjà : « {existing_title} » (id={existing_id}). "
                    "Utilise « + Rattacher un document » au lieu de le ré-importer."
                ),
            )
        # Orphan — purge it before inserting the new row. (Cascade-delete
        # tags + links so we don't keep stale references.)
        await db.execute("DELETE FROM document_tags WHERE document_id = ?", (existing_id,))
        await db.execute(
            "DELETE FROM document_links WHERE source_id = ? OR target_id = ?",
            (existing_id, existing_id),
        )
        await db.execute("DELETE FROM documents WHERE id = ?", (existing_id,))
        # No commit yet — gets bundled with the INSERT below.

    # Resolve supplier_id : explicit ID wins, fall back to name lookup for
    # legacy callers (uploads from the old flat view sent only the name).
    if not supplier_id and supplier:
        rows = await db.execute_fetchall(
            "SELECT id FROM suppliers WHERE name LIKE ?", (f"%{supplier}%",)
        )
        if rows:
            supplier_id = rows[0][0]

    now = datetime.now().isoformat(timespec="seconds")
    year_for_ref = (doc_date or now)[:4]
    internal_ref = await _next_internal_ref(db, doc_type, year_for_ref)
    acompte_flag = 1 if is_acompte else 0
    cursor = await db.execute(
        """INSERT INTO documents (title, doc_type, supplier_id, doc_date, reference, internal_ref, file_path, file_hash, notes, created_at, is_acompte)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, doc_type, supplier_id, doc_date, reference, internal_ref, rel_path, sha, notes, now, acompte_flag),
    )
    new_doc_id = cursor.lastrowid
    # Persist tags from the comma-separated string. The upload endpoint accepted them
    # but never wrote them to document_tags before — this is the missing link.
    if tags:
        await _attach_tags_by_name(db, new_doc_id, tags, now)
    # Optional immediate link to another doc — saves the user a separate step.
    if link_to_id:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO document_links (source_id, target_id, link_type, created_at) VALUES (?, ?, ?, ?)",
                (new_doc_id, int(link_to_id), "related", now),
            )
        except Exception as e:
            logger.warning(f"could not auto-link doc {new_doc_id} to {link_to_id}: {e}")
    await db.commit()
    return await _fetch_document_response(db, new_doc_id)


async def _attach_tags_by_name(db, doc_id: int, tags_str: str, now: str) -> None:
    """Split a comma-separated tag string, ensure each tag exists in `tags`, and link
    them to the doc via `document_tags`. No-op for blank input."""
    names = [t.strip() for t in (tags_str or "").split(",") if t.strip()]
    for name in names:
        rows = await db.execute_fetchall("SELECT id FROM tags WHERE name = ?", (name,))
        if rows:
            tag_id = rows[0][0]
        else:
            cur = await db.execute(
                "INSERT INTO tags (name, created_at) VALUES (?, ?)", (name, now),
            )
            tag_id = cur.lastrowid
        await db.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
            (doc_id, tag_id),
        )


@router.post("/upload-folder", status_code=201)
async def upload_folder(
    files: List[UploadFile] = File(...),
    doc_type: str = Form(""),
    supplier: str = Form(""),
    tags: str = Form(""),
    db=Depends(get_raw_db),
):
    """Upload multiple files at once (folder import)."""
    # Resolve supplier_id from name if provided
    supplier_id = None
    if supplier:
        rows = await db.execute_fetchall(
            "SELECT id FROM suppliers WHERE name LIKE ?", (f"%{supplier}%",)
        )
        if rows:
            supplier_id = rows[0][0]

    created = []
    skipped = 0
    now = datetime.now().isoformat(timespec="seconds")

    for file in files:
        filename = file.filename or "document"
        file_doc_type = doc_type or _detect_doc_type(filename)
        file_date = _detect_date(filename)
        file_title = Path(filename).stem.replace("_", " ").replace("-", " ").strip()

        try:
            rel_path, sha = await _store_file(file, file_doc_type)
        except HTTPException:
            skipped += 1
            continue

        # Skip duplicates silently in batch mode
        existing = await db.execute_fetchall(
            "SELECT id FROM documents WHERE file_hash = ?", (sha,)
        )
        if existing:
            skipped += 1
            continue

        year_for_ref = (file_date or now)[:4]
        internal_ref = await _next_internal_ref(db, file_doc_type, year_for_ref)
        cursor = await db.execute(
            """INSERT INTO documents (title, doc_type, supplier_id, doc_date, reference, internal_ref, file_path, file_hash, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_title, file_doc_type, supplier_id, file_date, "", internal_ref, rel_path, sha, "", now),
        )
        new_id = cursor.lastrowid
        if tags:
            await _attach_tags_by_name(db, new_id, tags, now)
        created.append(new_id)

    await db.commit()
    return {"created": len(created), "skipped": skipped, "ids": created}


# ── Preview (static prefix, must come BEFORE /{doc_id}) ────────


@router.get("/preview/{doc_id}")
async def preview_document_alt(doc_id: int, db=Depends(get_raw_db)):
    """Alternative preview route (kept for compat)."""
    return await _serve_preview(db, doc_id)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    search: str = Query(""),
    doc_type: str = Query(""),
    supplier_id: int | None = Query(None),
    db=Depends(get_raw_db),
):
    query = """SELECT d.id, d.title, COALESCE(d.doc_type,''), d.supplier_id,
                      COALESCE(s.name,'') as supplier_name,
                      d.doc_date, COALESCE(d.reference,''),
                      COALESCE(d.file_path,''), COALESCE(d.file_hash,''),
                      COALESCE(d.notes,''), COALESCE(d.created_at,''),
                      COALESCE(
                        (SELECT GROUP_CONCAT(t.name, ', ')
                         FROM document_tags dt JOIN tags t ON dt.tag_id = t.id
                         WHERE dt.document_id = d.id), '') AS tags_csv,
                      COALESCE(d.internal_ref, '') AS internal_ref,
                      COALESCE(d.is_acompte, 0) AS is_acompte
               FROM documents d
               LEFT JOIN suppliers s ON d.supplier_id = s.id
               WHERE 1=1"""
    params: list = []

    if search:
        # Match against title, external reference, internal reference, and notes —
        # so a user can paste either "DEV-2026-001" or "F16347" and find the doc.
        query += " AND (d.title LIKE ? OR d.reference LIKE ? OR d.internal_ref LIKE ? OR d.notes LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"]

    if doc_type:
        query += " AND d.doc_type = ?"
        params.append(doc_type)

    if supplier_id is not None:
        query += " AND d.supplier_id = ?"
        params.append(supplier_id)

    query += " ORDER BY d.created_at DESC"

    rows = await db.execute_fetchall(query, params)
    return [DocumentResponse(**_row_to_document(r)) for r in rows]


@router.get("/{doc_id}")
async def get_document(doc_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        """SELECT d.id, d.title, COALESCE(d.doc_type,''), d.supplier_id,
                  COALESCE(s.name,'') as supplier_name,
                  d.doc_date, COALESCE(d.reference,''),
                  COALESCE(d.file_path,''), COALESCE(d.file_hash,''),
                  COALESCE(d.notes,''), COALESCE(d.created_at,''),
                  '' AS tags_csv,
                  COALESCE(d.internal_ref, '') AS internal_ref,
                  COALESCE(d.is_acompte, 0) AS is_acompte
           FROM documents d
           LEFT JOIN suppliers s ON d.supplier_id = s.id
           WHERE d.id = ?""",
        (doc_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = _row_to_document(rows[0])
    # `tags` is fetched separately as a full TagResponse list below — strip the CSV
    # string from doc so we don't get a kwargs collision in DocumentDetailResponse.
    doc.pop("tags", None)

    # Fetch tags
    tag_rows = await db.execute_fetchall(
        """SELECT t.id, t.name, COALESCE(t.created_at,'')
           FROM tags t
           JOIN document_tags dt ON dt.tag_id = t.id
           WHERE dt.document_id = ?
           ORDER BY t.name ASC""",
        (doc_id,),
    )
    tags = [TagResponse(id=r[0], name=r[1], created_at=r[2]) for r in tag_rows]

    # Fetch links
    link_rows = await db.execute_fetchall(
        """SELECT id, source_id, target_id, COALESCE(link_type,''), COALESCE(created_at,'')
           FROM document_links
           WHERE source_id = ? OR target_id = ?""",
        (doc_id, doc_id),
    )
    links = [
        DocumentLinkResponse(
            id=r[0], source_id=r[1], target_id=r[2], link_type=r[3], created_at=r[4]
        )
        for r in link_rows
    ]

    # Fetch linked projects
    linked_projects = []
    try:
        proj_rows = await db.execute_fetchall(
            """SELECT p.id, p.title, p.color FROM projects p
               JOIN project_documents pd ON p.id = pd.project_id
               WHERE pd.document_id = ?""",
            (doc_id,),
        )
        linked_projects = [{"id": r[0], "title": r[1], "color": r[2]} for r in proj_rows]
    except Exception as e:
        # Don't 500 the document detail just because project links can't be resolved,
        # but log so we can spot a real schema/permission problem.
        logger.warning(f"could not fetch linked projects for doc {doc_id}: {e}")

    result = DocumentDetailResponse(**doc, tags=tags, links=links)
    # Add projects as extra field (not in Pydantic model, use dict)
    result_dict = result.model_dump()
    result_dict["projects"] = linked_projects
    return result_dict


@router.get("/{doc_id}/preview")
async def preview_document(doc_id: int, db=Depends(get_raw_db)):
    """Serve the document file from the vault for inline preview."""
    return await _serve_preview(db, doc_id)


async def _resolve_supplier_id(db, supplier_id, supplier_name):
    """If supplier_id not given but a name is, look it up (exact first, then LIKE)."""
    if supplier_id is not None:
        return supplier_id
    name = (supplier_name or "").strip()
    if not name:
        return None
    rows = await db.execute_fetchall("SELECT id FROM suppliers WHERE name = ?", (name,))
    if rows:
        return rows[0][0]
    rows = await db.execute_fetchall("SELECT id FROM suppliers WHERE name LIKE ? ORDER BY length(name) ASC LIMIT 1", (f"%{name}%",))
    if rows:
        return rows[0][0]
    return None


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(body: DocumentCreate, db=Depends(get_raw_db)):
    now = datetime.now().isoformat(timespec="seconds")
    supplier_id = await _resolve_supplier_id(db, body.supplier_id, body.supplier)
    cursor = await db.execute(
        """INSERT INTO documents (title, doc_type, supplier_id, doc_date, reference, file_path, file_hash, notes, created_at, is_acompte)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            body.title,
            body.doc_type,
            supplier_id,
            body.doc_date,
            body.reference,
            body.file_path,
            body.file_hash,
            body.notes,
            now,
            1 if body.is_acompte else 0,
        ),
    )
    await db.commit()
    doc_id = cursor.lastrowid

    # Insert tags
    for tag_id in body.tag_ids:
        await db.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
            (doc_id, tag_id),
        )
    if body.tag_ids:
        await db.commit()

    return await _fetch_document_response(db, doc_id)


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: int, body: DocumentUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM documents WHERE id = ?", (doc_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")

    supplier_id = await _resolve_supplier_id(db, body.supplier_id, body.supplier)
    await db.execute(
        """UPDATE documents SET title=?, doc_type=?, supplier_id=?, doc_date=?, reference=?, file_path=?, file_hash=?, notes=?, is_acompte=?
           WHERE id=?""",
        (
            body.title,
            body.doc_type,
            supplier_id,
            body.doc_date,
            body.reference,
            body.file_path,
            body.file_hash,
            body.notes,
            1 if body.is_acompte else 0,
            doc_id,
        ),
    )

    # Update tags: delete old, insert new
    await db.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
    for tag_id in body.tag_ids:
        await db.execute(
            "INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)",
            (doc_id, tag_id),
        )
    await db.commit()

    return await _fetch_document_response(db, doc_id)


@router.post("/cleanup-orphans")
async def cleanup_orphan_documents(db=Depends(get_raw_db)):
    """v7.0.7 — delete DB rows whose underlying file is missing on disk.

    Returns the count + IDs of rows removed. Used as a one-shot cleanup
    triggered from the UI (button in the "Rattacher un document" dialog).
    Safe to run anytime: only touches rows whose `file_path` points to a
    file that no longer exists.
    """
    rows = await db.execute_fetchall(
        "SELECT id, COALESCE(file_path, '') FROM documents"
    )
    removed: list[int] = []
    for r in rows:
        did = r[0]
        rel = r[1]
        if not rel:
            continue
        if (VAULT_ROOT / rel).exists():
            continue
        # Cascade: tags + links + dossier link kept by ON DELETE SET NULL.
        await db.execute("DELETE FROM document_tags WHERE document_id = ?", (did,))
        await db.execute(
            "DELETE FROM document_links WHERE source_id = ? OR target_id = ?",
            (did, did),
        )
        await db.execute("DELETE FROM documents WHERE id = ?", (did,))
        removed.append(did)
    if removed:
        await db.commit()
    return {"removed": len(removed), "ids": removed}


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM documents WHERE id = ?", (doc_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
    await db.execute(
        "DELETE FROM document_links WHERE source_id = ? OR target_id = ?",
        (doc_id, doc_id),
    )
    await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    await db.commit()


# ── Amounts (v7.0.1) ─────────────────────────────────────────────
# Amounts are now first-class fields on the document itself (so a doc not
# linked to any project still carries its devis/facture amount). project_documents
# remains the per-project override for the legacy ProjectsPage view.

@router.put("/{doc_id}/amount")
async def update_document_amount(doc_id: int, body: dict, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM documents WHERE id = ?", (doc_id,))
    if not rows:
        raise HTTPException(404, "Document introuvable")
    try:
        amount = float(body.get("amount") or 0)
        amount_accepted = float(body.get("amount_accepted") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Montants invalides")

    await db.execute(
        "UPDATE documents SET amount = ?, amount_accepted = ? WHERE id = ?",
        (amount, amount_accepted, doc_id),
    )
    # Keep project_documents in sync so the ProjectsPage budget panel reflects
    # the change without us touching it.
    await db.execute(
        "UPDATE project_documents SET amount = ?, amount_accepted = ? WHERE document_id = ?",
        (amount, amount_accepted, doc_id),
    )
    await db.commit()
    return {"id": doc_id, "amount": amount, "amount_accepted": amount_accepted}


# ── Document Links ──────────────────────────────────────────────


@router.get("/{doc_id}/links", response_model=list[DocumentLinkResponse])
async def get_document_links(doc_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        """SELECT id, source_id, target_id, COALESCE(link_type,''), COALESCE(created_at,'')
           FROM document_links
           WHERE source_id = ? OR target_id = ?""",
        (doc_id, doc_id),
    )
    return [
        DocumentLinkResponse(
            id=r[0], source_id=r[1], target_id=r[2], link_type=r[3], created_at=r[4]
        )
        for r in rows
    ]


@router.post("/{doc_id}/links", response_model=DocumentLinkResponse, status_code=201)
async def create_document_link(
    doc_id: int, body: DocumentLinkCreate, db=Depends(get_raw_db)
):
    # Verify both documents exist
    for did in (doc_id, body.target_id):
        rows = await db.execute_fetchall(
            "SELECT id FROM documents WHERE id = ?", (did,)
        )
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"Document {did} not found"
            )

    now = datetime.now().isoformat(timespec="seconds")
    cursor = await db.execute(
        """INSERT INTO document_links (source_id, target_id, link_type, created_at)
           VALUES (?, ?, ?, ?)""",
        (doc_id, body.target_id, body.link_type, now),
    )
    await db.commit()
    return DocumentLinkResponse(
        id=cursor.lastrowid,
        source_id=doc_id,
        target_id=body.target_id,
        link_type=body.link_type,
        created_at=now,
    )


async def _serve_preview(db, doc_id: int):
    """Serve a document file from the vault."""
    rows = await db.execute_fetchall(
        "SELECT file_path FROM documents WHERE id = ?", (doc_id,)
    )
    if not rows or not rows[0][0]:
        raise HTTPException(status_code=404, detail="Document or file not found")

    rel_path = rows[0][0]
    full_path = VAULT_ROOT / rel_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {rel_path}")

    ext = full_path.suffix.lower()
    media_type = MIME_MAP.get(ext, "application/octet-stream")
    content = full_path.read_bytes()
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{full_path.name}"',
        },
    )


async def _fetch_document_response(db, doc_id: int) -> DocumentResponse:
    rows = await db.execute_fetchall(
        """SELECT d.id, d.title, COALESCE(d.doc_type,''), d.supplier_id,
                  COALESCE(s.name,'') as supplier_name,
                  d.doc_date, COALESCE(d.reference,''),
                  COALESCE(d.file_path,''), COALESCE(d.file_hash,''),
                  COALESCE(d.notes,''), COALESCE(d.created_at,''),
                  COALESCE(
                    (SELECT GROUP_CONCAT(t.name, ', ')
                     FROM document_tags dt JOIN tags t ON dt.tag_id = t.id
                     WHERE dt.document_id = d.id), '') AS tags_csv,
                  COALESCE(d.internal_ref, '') AS internal_ref,
                  COALESCE(d.is_acompte, 0) AS is_acompte
           FROM documents d
           LEFT JOIN suppliers s ON d.supplier_id = s.id
           WHERE d.id = ?""",
        (doc_id,),
    )
    return DocumentResponse(**_row_to_document(rows[0]))
