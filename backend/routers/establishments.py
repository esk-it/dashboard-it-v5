"""Establishments router — manages the 3 schools the IT manager handles
(Lycée Notre Dame du Kreisker, Collège Sainte Ursule, Collège Notre Dame
d'Espérance). Each establishment has a stable `code` (NDK / SU / NDE) used
by other modules (tasks.site, projects.site, planning_events.site) to
reference it, plus a logo, color, optional name/aliases.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ..database import get_raw_db

router = APIRouter(prefix="/api/establishments", tags=["establishments"])

# Logo directory — kept separate from supplier logos so listings/backups stay
# clean. Matches the path layout used by suppliers (data/logos), with our
# own folder.
if os.environ.get("ITMANAGER_DATA_DIR"):
    LOGO_DIR = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data" / "establishments"
else:
    LOGO_DIR = Path(__file__).parent.parent / "data" / "establishments"
LOGO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


class EstablishmentUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    aliases: list[str] | None = None  # free-form strings used to match foreign data (e.g. GLPI location)


def _row_to_dict(r) -> dict:
    """Decode an establishments row into the public API shape."""
    try:
        aliases = json.loads(r[5]) if r[5] else []
        if not isinstance(aliases, list):
            aliases = []
    except Exception:
        aliases = []
    return {
        "id": r[0],
        "code": r[1],
        "name": r[2],
        "color": r[3],
        "logo_path": r[4],
        "has_logo": bool(r[4]),
        "aliases": aliases,
        "sort_order": r[6],
    }


@router.get("")
async def list_establishments(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, code, name, color, logo_path, aliases, sort_order FROM establishments ORDER BY sort_order ASC, id ASC"
    )
    return [_row_to_dict(r) for r in rows]


@router.put("/{establishment_id}")
async def update_establishment(establishment_id: int, payload: EstablishmentUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id FROM establishments WHERE id = ?", (establishment_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Établissement introuvable")

    updates: list[str] = []
    params: list = []
    if payload.name is not None:
        updates.append("name = ?")
        params.append(payload.name.strip())
    if payload.color is not None:
        updates.append("color = ?")
        params.append(payload.color)
    if payload.aliases is not None:
        # Normalise: strip, drop empty, de-duplicate keeping insertion order.
        seen: set[str] = set()
        cleaned: list[str] = []
        for a in payload.aliases:
            s = (a or "").strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                cleaned.append(s)
        updates.append("aliases = ?")
        params.append(json.dumps(cleaned, ensure_ascii=False))

    if updates:
        params.append(establishment_id)
        await db.execute(
            f"UPDATE establishments SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        await db.commit()

    rows = await db.execute_fetchall(
        "SELECT id, code, name, color, logo_path, aliases, sort_order FROM establishments WHERE id = ?",
        (establishment_id,),
    )
    return _row_to_dict(rows[0])


@router.post("/{establishment_id}/logo")
async def upload_logo(establishment_id: int, file: UploadFile = File(...), db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT logo_path FROM establishments WHERE id = ?", (establishment_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Établissement introuvable")

    ext = Path(file.filename or "upload.png").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format {ext} non autorisé (png/jpg/svg/webp acceptés)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")
    hash8 = hashlib.md5(content).hexdigest()[:8]
    filename = f"{establishment_id}_{hash8}{ext}"

    # Remove the previous logo file so the disk doesn't accumulate orphans
    # (only the most recent upload is referenced by the row).
    old_path = rows[0][0]
    if old_path:
        old_file = LOGO_DIR / old_path
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                pass  # best effort — keep going even if the OS holds the file open

    (LOGO_DIR / filename).write_bytes(content)

    await db.execute(
        "UPDATE establishments SET logo_path = ? WHERE id = ?",
        (filename, establishment_id),
    )
    await db.commit()

    rows = await db.execute_fetchall(
        "SELECT id, code, name, color, logo_path, aliases, sort_order FROM establishments WHERE id = ?",
        (establishment_id,),
    )
    return _row_to_dict(rows[0])


@router.delete("/{establishment_id}/logo")
async def delete_logo(establishment_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT logo_path FROM establishments WHERE id = ?", (establishment_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Établissement introuvable")

    old_path = rows[0][0]
    if old_path:
        old_file = LOGO_DIR / old_path
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                pass

    await db.execute(
        "UPDATE establishments SET logo_path = '' WHERE id = ?", (establishment_id,)
    )
    await db.commit()
    return {"ok": True}


@router.get("/{establishment_id}/logo")
async def serve_logo(establishment_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT logo_path FROM establishments WHERE id = ?", (establishment_id,)
    )
    if not rows or not rows[0][0]:
        raise HTTPException(status_code=404, detail="Logo absent")

    logo_path = LOGO_DIR / rows[0][0]
    if not logo_path.exists():
        raise HTTPException(status_code=404, detail="Fichier logo introuvable")

    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    media_type = media_types.get(logo_path.suffix.lower(), "application/octet-stream")
    return Response(
        content=logo_path.read_bytes(),
        media_type=media_type,
        headers={
            "Content-Disposition": "inline",
            # Static enough that a short cache helps avoid request spam from
            # every list render — but short enough that an upload reflects
            # quickly. 1 minute is a fine compromise.
            "Cache-Control": "public, max-age=60",
        },
    )
