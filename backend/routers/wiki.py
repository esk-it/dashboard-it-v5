from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

from ..database import get_raw_db
from ..schemas.wiki import (
    WikiArticleCreate,
    WikiArticleListResponse,
    WikiArticleResponse,
    WikiArticleUpdate,
    WikiCategoryResponse,
)

router = APIRouter(prefix="/api/wiki", tags=["wiki"])

# Custom segments storage
if os.environ.get("ITMANAGER_DATA_DIR"):
    _DATA_DIR = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data"
else:
    _DATA_DIR = Path(__file__).parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CUSTOM_SEGMENTS_FILE = _DATA_DIR / "wiki_segments.json"


@router.get("/categories", response_model=list[WikiCategoryResponse])
async def list_categories(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        """SELECT id, name, COALESCE(color_hex,''), COALESCE(icon_key,''), sort_order
           FROM wiki_categories
           ORDER BY sort_order ASC, name ASC"""
    )
    return [
        WikiCategoryResponse(
            id=r[0], name=r[1], color_hex=r[2], icon_key=r[3], sort_order=r[4]
        )
        for r in rows
    ]


@router.get("", response_model=list[WikiArticleListResponse])
async def list_articles(
    category: str = Query(""),
    search: str = Query(""),
    pinned: bool | None = Query(None),
    db=Depends(get_raw_db),
):
    query = """SELECT id, title, COALESCE(category,''), pinned,
                      COALESCE(tags,''), COALESCE(updated_at,''),
                      COALESCE(content_format,'html')
               FROM wiki_articles
               WHERE 1=1"""
    params: list = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if search:
        query += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    if pinned is not None:
        query += " AND pinned = ?"
        params.append(1 if pinned else 0)

    query += " ORDER BY pinned DESC, updated_at DESC"

    rows = await db.execute_fetchall(query, params)
    return [
        WikiArticleListResponse(
            id=r[0], title=r[1], category=r[2], pinned=bool(r[3]),
            tags=r[4], updated_at=r[5], content_format=r[6],
        )
        for r in rows
    ]


# ── Reference parsing (dynamic segments) ────────────────────
_BASE_SEGMENT_LABELS = {
    # Types
    "PROC": "Procedure", "DOC": "Documentation", "GUIDE": "Guide", "FORM": "Formulaire", "NOTE": "Note",
    "OLD": "Ancien",
    # Domains
    "SI": "Systeme d'Info", "RES": "Reseau", "SEC": "Securite", "PED": "Pedagogique",
    "ADM": "Administration", "TEL": "Telephonie", "IMP": "Impression", "SRV": "Serveurs",
    # Actions
    "INST": "Installation", "CONF": "Configuration", "MAJ": "Mise a jour", "DIAG": "Diagnostic",
    "DEPL": "Deploiement", "SAV": "Sauvegarde", "BACKUP": "Sauvegarde", "REST": "Restauration",
    "SUPP": "Support", "CREA": "Creation", "MIGR": "Migration", "SECU": "Securisation",
    "UTIL": "Utilisation", "CUST": "Personnalisation", "GIT": "Git",
    "HTTPS": "HTTPS/SSL", "SYNC": "Synchronisation", "UPDATE": "Mise a jour",
    "INVENTORY": "Inventaire", "LDAP": "Annuaire LDAP", "MAIL": "Messagerie",
    "MAINT": "Maintenance", "RESET": "Reinitialisation", "TEST": "Test", "AUDIT": "Audit",
}

def _load_custom_segments() -> dict:
    if _CUSTOM_SEGMENTS_FILE.exists():
        try:
            return json.loads(_CUSTOM_SEGMENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_custom_segments(customs: dict):
    _CUSTOM_SEGMENTS_FILE.write_text(json.dumps(customs, indent=2, ensure_ascii=False), encoding="utf-8")

def _get_all_segments() -> dict:
    """Merge base segments with custom segments. Custom overrides base."""
    merged = dict(_BASE_SEGMENT_LABELS)
    merged.update(_load_custom_segments())
    return merged

def _learn_segment(code: str):
    """Auto-learn an unknown segment code by adding it to custom segments."""
    all_segs = _get_all_segments()
    if code not in all_segs:
        customs = _load_custom_segments()
        customs[code] = code  # Use code as default label
        _save_custom_segments(customs)

REF_PATTERN = re.compile(r'^([A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)*)')

def _parse_ref(title: str) -> dict | None:
    m = REF_PATTERN.match(title.strip())
    if not m:
        return None
    ref = m.group(1)
    parts = ref.split("-")
    if len(parts) < 2:
        return None
    all_segs = _get_all_segments()
    segments = [{"code": p, "label": all_segs.get(p, p)} for p in parts]
    # Auto-learn any unknown segments
    for p in parts:
        if p not in all_segs:
            _learn_segment(p)
    return {"ref": ref, "segments": segments}


# ── Reference endpoints (MUST be before /{article_id}) ────────
@router.get("/references/tree")
async def reference_tree(db=Depends(get_raw_db)):
    """Build a 4-level tree: Type → Domain → Tool → Articles (with action label)."""
    rows = await db.execute_fetchall(
        "SELECT id, title, COALESCE(category,''), COALESCE(tags,''), COALESCE(updated_at,'') FROM wiki_articles ORDER BY title"
    )
    # tree structure: { type_code: { label, domains: { domain_code: { label, tools: { tool_code: { label, articles: [] } } } } } }
    tree: dict = {}
    no_ref = []

    for r in rows:
        article = {"id": r[0], "title": r[1], "category": r[2], "tags": r[3], "updated_at": r[4]}
        parsed = _parse_ref(r[1])

        if parsed and len(parsed["segments"]) >= 3:
            segs = parsed["segments"]
            type_code = segs[0]["code"]
            domain_code = segs[1]["code"]
            tool_code = segs[2]["code"]
            # Action is segment[3] if exists, otherwise empty
            action_code = segs[3]["code"] if len(segs) >= 4 else ""
            action_label = segs[3]["label"] if len(segs) >= 4 else ""

            article["ref"] = parsed["ref"]
            article["segments"] = segs
            article["action_code"] = action_code
            article["action_label"] = action_label
            # Strip reference from title for clean display
            clean_title = r[1][len(parsed["ref"]):].lstrip(" -–—")
            article["clean_title"] = clean_title or r[1]

            # Build nested tree
            if type_code not in tree:
                tree[type_code] = {"label": segs[0]["label"], "domains": {}}
            domains = tree[type_code]["domains"]
            if domain_code not in domains:
                domains[domain_code] = {"label": segs[1]["label"], "tools": {}}
            tools = domains[domain_code]["tools"]
            if tool_code not in tools:
                tools[tool_code] = {"label": segs[2]["label"], "articles": []}
            tools[tool_code]["articles"].append(article)
        else:
            article["ref"] = parsed["ref"] if parsed else None
            article["segments"] = parsed["segments"] if parsed else []
            article["clean_title"] = r[1]
            no_ref.append(article)

    return {"tree": tree, "unclassified": no_ref}


@router.get("/references/segments")
async def reference_segments(db=Depends(get_raw_db)):
    all_segs = _get_all_segments()
    rows = await db.execute_fetchall("SELECT title FROM wiki_articles")
    types, domains, tools, actions = set(), set(), set(), set()
    for r in rows:
        parsed = _parse_ref(r[0])
        if parsed and len(parsed["segments"]) >= 2:
            types.add(parsed["segments"][0]["code"])
            domains.add(parsed["segments"][1]["code"])
            if len(parsed["segments"]) >= 3:
                tools.add(parsed["segments"][2]["code"])
            if len(parsed["segments"]) >= 4:
                actions.add(parsed["segments"][3]["code"])
    # Also include all known segments (base + custom) so they show in dropdowns
    for code in all_segs:
        if code in ("PROC", "DOC", "GUIDE", "FORM", "NOTE", "OLD"):
            types.add(code)
        elif code in ("SI", "RES", "SEC", "PED", "ADM", "TEL", "IMP", "SRV"):
            domains.add(code)
    def to_list(s):
        return [{"code": c, "label": all_segs.get(c, c)} for c in sorted(s)]
    return {"types": to_list(types), "domains": to_list(domains), "tools": to_list(tools), "actions": to_list(actions)}


@router.post("/references/segments")
async def add_custom_segment(body: dict = Body(...)):
    """Add a custom segment code with a label."""
    code = body.get("code", "").strip().upper()
    label = body.get("label", "").strip()
    if not code or len(code) < 2:
        raise HTTPException(400, "Code must be at least 2 characters")
    if not label:
        label = code
    customs = _load_custom_segments()
    customs[code] = label
    _save_custom_segments(customs)
    return {"ok": True, "code": code, "label": label}


# ── Single article (AFTER references/* to avoid route conflict) ──
@router.get("/{article_id}", response_model=WikiArticleResponse)
async def get_article(article_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        """SELECT id, title, COALESCE(category,''), COALESCE(content,''),
                  COALESCE(tags,''), pinned, COALESCE(created_at,''),
                  COALESCE(updated_at,''), COALESCE(source_path,''),
                  COALESCE(content_format,'html')
           FROM wiki_articles WHERE id = ?""",
        (article_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Wiki article not found")
    r = rows[0]
    return WikiArticleResponse(
        id=r[0], title=r[1], category=r[2], content=r[3], tags=r[4],
        pinned=bool(r[5]), created_at=r[6], updated_at=r[7], source_path=r[8],
        content_format=r[9],
    )


@router.get("/{article_id}/export")
async def export_article_md(article_id: int, db=Depends(get_raw_db)):
    """Export a wiki article as a .md file download."""
    rows = await db.execute_fetchall(
        "SELECT title, COALESCE(content,''), COALESCE(content_format,'html') FROM wiki_articles WHERE id = ?",
        (article_id,),
    )
    if not rows:
        raise HTTPException(404, "Article not found")
    title, content, fmt = rows[0]

    # If content is HTML, do a basic conversion to markdown
    if fmt == "html" and content:
        import re as _re
        md = content
        md = _re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", md)
        md = _re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", md)
        md = _re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", md)
        md = _re.sub(r"<strong>(.*?)</strong>", r"**\1**", md)
        md = _re.sub(r"<b>(.*?)</b>", r"**\1**", md)
        md = _re.sub(r"<em>(.*?)</em>", r"*\1*", md)
        md = _re.sub(r"<i>(.*?)</i>", r"*\1*", md)
        md = _re.sub(r"<code>(.*?)</code>", r"`\1`", md)
        md = _re.sub(r"<br\s*/?>", "\n", md)
        md = _re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", md)
        md = _re.sub(r"<[^>]+>", "", md)  # strip remaining tags
        md = _re.sub(r"\n{3,}", "\n\n", md)  # collapse extra newlines
        content = md.strip()
    else:
        content = content or ""

    # Add title as H1 header
    md_content = f"# {title}\n\n{content}\n"

    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    filename = f"{safe_title}.md"

    return Response(
        content=md_content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=WikiArticleResponse, status_code=201)
async def create_article(body: WikiArticleCreate, db=Depends(get_raw_db)):
    now = datetime.now().isoformat(timespec="seconds")
    cursor = await db.execute(
        """INSERT INTO wiki_articles (title, category, content, tags, pinned, created_at, updated_at, source_path, content_format)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            body.title,
            body.category,
            body.content,
            body.tags,
            1 if body.pinned else 0,
            now,
            now,
            body.source_path,
            body.content_format,
        ),
    )
    await db.commit()
    article_id = cursor.lastrowid
    return await get_article(article_id, db)


@router.put("/{article_id}", response_model=WikiArticleResponse)
async def update_article(article_id: int, body: WikiArticleUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM wiki_articles WHERE id = ?", (article_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Wiki article not found")

    now = datetime.now().isoformat(timespec="seconds")
    await db.execute(
        """UPDATE wiki_articles SET title=?, category=?, content=?, tags=?, pinned=?, updated_at=?, source_path=?, content_format=?
           WHERE id=?""",
        (
            body.title,
            body.category,
            body.content,
            body.tags,
            1 if body.pinned else 0,
            now,
            body.source_path,
            body.content_format,
            article_id,
        ),
    )
    await db.commit()
    return await get_article(article_id, db)


@router.delete("/{article_id}", status_code=204)
async def delete_article(article_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM wiki_articles WHERE id = ?", (article_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Wiki article not found")

    await db.execute("DELETE FROM wiki_articles WHERE id = ?", (article_id,))
    await db.commit()


    # Old reference endpoints removed — now defined before /{article_id}


@router.get("/{article_id}/related")
async def related_articles(article_id: int, db=Depends(get_raw_db)):
    """Find related articles sharing the same tool or domain."""
    rows = await db.execute_fetchall(
        "SELECT title FROM wiki_articles WHERE id = ?", (article_id,)
    )
    if not rows:
        return []

    parsed = _parse_ref(rows[0][0])
    if not parsed or len(parsed["segments"]) < 3:
        return []

    # Find articles sharing the same tool (segment[2])
    tool_code = parsed["segments"][2]["code"]
    domain_code = parsed["segments"][1]["code"]

    all_articles = await db.execute_fetchall(
        "SELECT id, title, COALESCE(category,''), COALESCE(updated_at,'') FROM wiki_articles WHERE id != ? ORDER BY title",
        (article_id,)
    )

    related = []
    for r in all_articles:
        p = _parse_ref(r[1])
        if not p or len(p["segments"]) < 3:
            continue
        # Same tool = strong match, same domain = weak match
        if p["segments"][2]["code"] == tool_code:
            related.append({"id": r[0], "title": r[1], "category": r[2], "updated_at": r[3], "match": "tool", "ref": p["ref"]})
        elif p["segments"][1]["code"] == domain_code:
            related.append({"id": r[0], "title": r[1], "category": r[2], "updated_at": r[3], "match": "domain", "ref": p["ref"]})

    # Sort: tool matches first, then domain
    related.sort(key=lambda x: (0 if x["match"] == "tool" else 1, x["title"]))
    return related[:10]
