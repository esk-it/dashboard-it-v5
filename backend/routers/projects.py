"""Projects module — CRUD + links to tasks, documents, suppliers."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from ..database import get_raw_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Models ──

class ProjectCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "not_started"
    color: str = "#3B82F6"
    start_date: str = ""
    end_date: str = ""
    budget: float = 0
    budget_spent: float = 0


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    color: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    budget: float | None = None
    budget_spent: float | None = None


class NoteCreate(BaseModel):
    content: str


# ── Helpers ──

def _now():
    return datetime.now().isoformat(timespec="seconds")


async def _project_dict(db, row) -> dict:
    """Build a project dict with computed stats."""
    pid = row[0]
    total_tasks = 0
    done_tasks = 0
    doc_count = 0
    sup_count = 0

    try:
        tasks_rows = await db.execute_fetchall(
            "SELECT COUNT(*), SUM(CASE WHEN done=1 THEN 1 ELSE 0 END) FROM tasks WHERE project_id=?", (pid,)
        )
        total_tasks = tasks_rows[0][0] or 0
        done_tasks = int(tasks_rows[0][1] or 0)
    except Exception:
        pass  # project_id column may not exist yet

    try:
        doc_count = (await db.execute_fetchall(
            "SELECT COUNT(*) FROM project_documents WHERE project_id=?", (pid,)
        ))[0][0]
    except Exception:
        pass

    try:
        sup_count = (await db.execute_fetchall(
            "SELECT COUNT(*) FROM project_suppliers WHERE project_id=?", (pid,)
        ))[0][0]
    except Exception:
        pass

    progress = round((done_tasks / total_tasks * 100) if total_tasks > 0 else 0)

    return {
        "id": pid,
        "title": row[1],
        "description": row[2],
        "status": row[3],
        "color": row[4],
        "start_date": row[5],
        "end_date": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "progress": progress,
        "document_count": doc_count,
        "supplier_count": sup_count,
        "budget": row[9] if len(row) > 9 else 0,
        "budget_spent": row[10] if len(row) > 10 else 0,
    }


# ── Stats (MUST be before /{project_id} to avoid route conflict) ──

@router.get("/stats/summary")
async def project_stats(db=Depends(get_raw_db)):
    try:
        rows = await db.execute_fetchall("SELECT status, COUNT(*) FROM projects GROUP BY status")
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        return {
            "total": total,
            "in_progress": counts.get("in_progress", 0),
            "not_started": counts.get("not_started", 0),
            "completed": counts.get("completed", 0),
            "paused": counts.get("paused", 0),
        }
    except Exception:
        return {"total": 0, "in_progress": 0, "not_started": 0, "completed": 0, "paused": 0}


# ── CRUD ──

@router.get("")
async def list_projects(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, title, description, status, color, start_date, end_date, created_at, updated_at, COALESCE(budget,0), COALESCE(budget_spent,0) "
        "FROM projects ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'not_started' THEN 1 WHEN 'paused' THEN 2 ELSE 3 END, updated_at DESC"
    )
    return [await _project_dict(db, r) for r in rows]


@router.post("")
async def create_project(body: ProjectCreate, db=Depends(get_raw_db)):
    now = _now()
    cursor = await db.execute(
        "INSERT INTO projects (title, description, status, color, start_date, end_date, budget, budget_spent, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (body.title, body.description, body.status, body.color, body.start_date, body.end_date, body.budget, body.budget_spent, now, now),
    )
    await db.commit()
    return {"ok": True, "id": cursor.lastrowid}


@router.get("/{project_id}")
async def get_project(project_id: int, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, title, description, status, color, start_date, end_date, created_at, updated_at, COALESCE(budget,0), COALESCE(budget_spent,0) FROM projects WHERE id=?",
        (project_id,),
    )
    if not rows:
        raise HTTPException(404, "Projet non trouve")
    project = await _project_dict(db, rows[0])

    # Get tasks (safely — project_id column may not exist)
    try:
        task_rows = await db.execute_fetchall(
            "SELECT id, title, category, priority, due_date, done, created_at, notes, site FROM tasks WHERE project_id=? ORDER BY done ASC, priority DESC, due_date ASC",
            (project_id,),
        )
        project["tasks"] = [
            {"id": r[0], "title": r[1], "category": r[2], "priority": r[3], "due_date": r[4],
             "done": bool(r[5]), "created_at": r[6], "notes": r[7], "site": r[8]}
            for r in task_rows
        ]
    except Exception as e:
        logger.warning(f"Failed to get tasks for project {project_id}: {e}")
        project["tasks"] = []

    # Get linked documents (safely)
    try:
        doc_rows = await db.execute_fetchall(
            """SELECT d.id, d.title, d.doc_type, d.doc_date, d.reference,
                      COALESCE(pd.amount, 0), COALESCE(pd.amount_accepted, 0), COALESCE(pd.status, '')
               FROM documents d JOIN project_documents pd ON d.id = pd.document_id
               WHERE pd.project_id=? ORDER BY d.doc_date DESC""",
            (project_id,),
        )
        project["documents"] = [
            {"id": r[0], "title": r[1], "doc_type": r[2], "doc_date": r[3], "reference": r[4],
             "amount": r[5], "amount_accepted": r[6], "status": r[7]}
            for r in doc_rows
        ]
    except Exception:
        project["documents"] = []

    # Get linked suppliers (safely)
    try:
        sup_rows = await db.execute_fetchall(
            """SELECT s.id, s.name, s.contact, s.phone, s.email
               FROM suppliers s JOIN project_suppliers ps ON s.id = ps.supplier_id
               WHERE ps.project_id=? ORDER BY s.name""",
            (project_id,),
        )
        project["suppliers"] = [
            {"id": r[0], "name": r[1], "contact": r[2], "phone": r[3], "email": r[4]}
            for r in sup_rows
        ]
    except Exception:
        project["suppliers"] = []

    # Get notes
    try:
        note_rows = await db.execute_fetchall(
            "SELECT id, content, created_at FROM project_notes WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        )
        project["notes"] = [
            {"id": r[0], "content": r[1], "created_at": r[2]}
            for r in note_rows
        ]
    except Exception:
        project["notes"] = []

    return project


@router.put("/{project_id}")
async def update_project(project_id: int, body: ProjectUpdate, db=Depends(get_raw_db)):
    updates, params = [], []
    for field in ("title", "description", "status", "color", "start_date", "end_date", "budget", "budget_spent"):
        val = getattr(body, field)
        if val is not None:
            updates.append(f"{field}=?")
            params.append(val)
    if updates:
        updates.append("updated_at=?")
        params.append(_now())
        params.append(project_id)
        await db.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id=?", tuple(params))
        await db.commit()
    return {"ok": True}


@router.delete("/{project_id}")
async def delete_project(project_id: int, db=Depends(get_raw_db)):
    # Unlink tasks (don't delete them, just remove project_id)
    await db.execute("UPDATE tasks SET project_id=NULL WHERE project_id=?", (project_id,))
    await db.execute("DELETE FROM project_documents WHERE project_id=?", (project_id,))
    await db.execute("DELETE FROM project_suppliers WHERE project_id=?", (project_id,))
    await db.execute("DELETE FROM project_notes WHERE project_id=?", (project_id,))
    await db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    await db.commit()
    return {"ok": True}


# ── Task linking ──

@router.post("/{project_id}/tasks")
async def add_task_to_project(project_id: int, body: dict = Body(...), db=Depends(get_raw_db)):
    """Create a new task linked to this project, or link an existing task."""
    try:
        task_id = body.get("task_id")
        if task_id:
            await db.execute("UPDATE tasks SET project_id=? WHERE id=?", (project_id, task_id))
        else:
            now = _now()
            # Get project name for the category tag
            proj_rows = await db.execute_fetchall("SELECT title FROM projects WHERE id=?", (project_id,))
            proj_name = proj_rows[0][0] if proj_rows else ""
            category = body.get("category", "") or f"Projet: {proj_name}"

            cursor = await db.execute(
                "INSERT INTO tasks (title, category, priority, due_date, done, created_at, notes, site, recurrence) VALUES (?,?,?,?,0,?,?,?,'') ",
                (body.get("title", ""), category, int(body.get("priority", 2)),
                 body.get("due_date") or None, now, body.get("notes", ""), body.get("site", "")),
            )
            task_id = cursor.lastrowid
            # Then link to project (will work even if project_id column was added via migration)
            try:
                await db.execute("UPDATE tasks SET project_id=? WHERE id=?", (project_id, task_id))
            except Exception:
                logger.warning(f"Could not set project_id on task {task_id} — column may not exist")
        await db.commit()
        return {"ok": True, "task_id": task_id}
    except Exception as e:
        logger.exception(f"Failed to add task to project {project_id}")
        raise HTTPException(502, f"Erreur creation tache: {e}")


@router.delete("/{project_id}/tasks/{task_id}")
async def unlink_task(project_id: int, task_id: int, db=Depends(get_raw_db)):
    """Unlink a task from the project (doesn't delete the task)."""
    await db.execute("UPDATE tasks SET project_id=NULL WHERE id=? AND project_id=?", (task_id, project_id))
    await db.commit()
    return {"ok": True}


# ── Document linking ──

@router.post("/{project_id}/documents")
async def link_document(project_id: int, body: dict = Body(...), db=Depends(get_raw_db)):
    doc_id = body.get("document_id")
    if not doc_id:
        raise HTTPException(400, "document_id requis")
    amount = float(body.get("amount", 0))
    amount_accepted = float(body.get("amount_accepted", 0))
    status = body.get("status", "")
    try:
        await db.execute(
            "INSERT INTO project_documents (project_id, document_id, amount, amount_accepted, status) VALUES (?,?,?,?,?)",
            (project_id, int(doc_id), amount, amount_accepted, status),
        )
        await db.commit()
    except Exception:
        # Already linked — update amounts
        try:
            await db.execute(
                "UPDATE project_documents SET amount=?, amount_accepted=?, status=? WHERE project_id=? AND document_id=?",
                (amount, amount_accepted, status, project_id, int(doc_id)),
            )
            await db.commit()
        except Exception:
            pass
    return {"ok": True}


@router.put("/{project_id}/documents/{document_id}")
async def update_document_link(project_id: int, document_id: int, body: dict = Body(...), db=Depends(get_raw_db)):
    """Update amount/status of a linked document."""
    try:
        await db.execute(
            "UPDATE project_documents SET amount=?, amount_accepted=?, status=? WHERE project_id=? AND document_id=?",
            (float(body.get("amount", 0)), float(body.get("amount_accepted", 0)),
             body.get("status", ""), project_id, document_id),
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to update doc link: {e}")
    return {"ok": True}


@router.delete("/{project_id}/documents/{document_id}")
async def unlink_document(project_id: int, document_id: int, db=Depends(get_raw_db)):
    await db.execute("DELETE FROM project_documents WHERE project_id=? AND document_id=?", (project_id, document_id))
    await db.commit()
    return {"ok": True}


# ── Supplier linking ──

@router.post("/{project_id}/suppliers")
async def link_supplier(project_id: int, body: dict = Body(...), db=Depends(get_raw_db)):
    sup_id = body.get("supplier_id")
    if not sup_id:
        raise HTTPException(400, "supplier_id requis")
    try:
        await db.execute("INSERT INTO project_suppliers (project_id, supplier_id) VALUES (?,?)", (project_id, int(sup_id)))
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to link supplier {sup_id} to project {project_id}: {e}")
    return {"ok": True}


@router.delete("/{project_id}/suppliers/{supplier_id}")
async def unlink_supplier(project_id: int, supplier_id: int, db=Depends(get_raw_db)):
    await db.execute("DELETE FROM project_suppliers WHERE project_id=? AND supplier_id=?", (project_id, supplier_id))
    await db.commit()
    return {"ok": True}


# ── Notes ──

@router.post("/{project_id}/notes")
async def add_note(project_id: int, body: NoteCreate, db=Depends(get_raw_db)):
    now = _now()
    cursor = await db.execute(
        "INSERT INTO project_notes (project_id, content, created_at) VALUES (?,?,?)",
        (project_id, body.content, now),
    )
    await db.commit()
    return {"ok": True, "id": cursor.lastrowid}


@router.delete("/{project_id}/notes/{note_id}")
async def delete_note(project_id: int, note_id: int, db=Depends(get_raw_db)):
    await db.execute("DELETE FROM project_notes WHERE id=? AND project_id=?", (note_id, project_id))
    await db.commit()
    return {"ok": True}


