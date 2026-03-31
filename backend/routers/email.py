"""Internal email/messaging system router."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..database import get_raw_db
from ..schemas.email import EmailCreate, EmailResponse, EmailUpdate, FolderCountResponse

router = APIRouter(prefix="/api/emails", tags=["emails"])

SECRET_KEY = os.environ.get("ITMANAGER_JWT_SECRET", "itmanager-dev-secret-key-change-me")
ALGORITHM = "HS256"

VALID_FOLDERS = ("inbox", "sent", "drafts", "trash")


# --------------- Helpers ---------------

def _get_current_user_id(request: Request) -> int:
    """Extract user ID from the Authorization header JWT token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")


def _row_to_email(row, sender_username: str = "", sender_display_name: str = "") -> dict:
    """Convert a DB row to an email dict."""
    recipients = []
    cc = []
    try:
        recipients = json.loads(row["recipients"]) if row["recipients"] else []
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        cc = json.loads(row["cc"]) if row["cc"] else []
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": row["id"],
        "sender_id": row["sender_id"],
        "sender_username": sender_username,
        "sender_display_name": sender_display_name,
        "recipients": recipients,
        "cc": cc,
        "subject": row["subject"] or "",
        "body": row["body"] or "",
        "folder": row["folder"] or "inbox",
        "is_read": bool(row["is_read"]),
        "is_starred": bool(row["is_starred"]),
        "created_at": row["created_at"] or "",
    }


# --------------- Routes ---------------

@router.get("/folders", response_model=list[FolderCountResponse])
async def list_folders(request: Request, db=Depends(get_raw_db)):
    """List folders with counts for the current user."""
    user_id = _get_current_user_id(request)

    results = []
    for folder in VALID_FOLDERS:
        if folder == "sent":
            # Sent folder: emails sent by current user
            count_row = await db.execute_fetchall(
                "SELECT COUNT(*) FROM emails WHERE sender_id = ? AND folder = 'sent'",
                (user_id,),
            )
            unread_row = await db.execute_fetchall(
                "SELECT COUNT(*) FROM emails WHERE sender_id = ? AND folder = 'sent' AND is_read = 0",
                (user_id,),
            )
        else:
            # Other folders: emails where current user is a recipient
            count_row = await db.execute_fetchall(
                """SELECT COUNT(*) FROM emails
                   WHERE (recipients LIKE ? OR recipients LIKE ?)
                   AND folder = ?""",
                (f'%"{user_id}"%', f'%{user_id}%', folder),
            )
            unread_row = await db.execute_fetchall(
                """SELECT COUNT(*) FROM emails
                   WHERE (recipients LIKE ? OR recipients LIKE ?)
                   AND folder = ? AND is_read = 0""",
                (f'%"{user_id}"%', f'%{user_id}%', folder),
            )

        count = count_row[0][0] if count_row else 0
        unread = unread_row[0][0] if unread_row else 0
        results.append(FolderCountResponse(folder=folder, count=count, unread=unread))

    return results


@router.get("", response_model=list[EmailResponse])
async def list_emails(
    request: Request,
    folder: str = Query("inbox"),
    search: str = Query(""),
    db=Depends(get_raw_db),
):
    """List emails in a folder for the current user."""
    user_id = _get_current_user_id(request)

    if folder not in VALID_FOLDERS:
        raise HTTPException(status_code=400, detail=f"Invalid folder. Must be one of: {', '.join(VALID_FOLDERS)}")

    if folder == "sent":
        query = """SELECT e.id, e.sender_id, e.recipients, e.cc, e.subject, e.body,
                          e.folder, e.is_read, e.is_starred, e.created_at,
                          u.username AS sender_username,
                          COALESCE(u.display_name, u.username) AS sender_display_name
                   FROM emails e
                   JOIN users u ON u.id = e.sender_id
                   WHERE e.sender_id = ? AND e.folder = 'sent'"""
        params: list = [user_id]
    elif folder == "drafts":
        query = """SELECT e.id, e.sender_id, e.recipients, e.cc, e.subject, e.body,
                          e.folder, e.is_read, e.is_starred, e.created_at,
                          u.username AS sender_username,
                          COALESCE(u.display_name, u.username) AS sender_display_name
                   FROM emails e
                   JOIN users u ON u.id = e.sender_id
                   WHERE e.sender_id = ? AND e.folder = 'drafts'"""
        params = [user_id]
    else:
        query = """SELECT e.id, e.sender_id, e.recipients, e.cc, e.subject, e.body,
                          e.folder, e.is_read, e.is_starred, e.created_at,
                          u.username AS sender_username,
                          COALESCE(u.display_name, u.username) AS sender_display_name
                   FROM emails e
                   JOIN users u ON u.id = e.sender_id
                   WHERE (e.recipients LIKE ? OR e.recipients LIKE ?)
                   AND e.folder = ?"""
        params = [f'%"{user_id}"%', f'%{user_id}%', folder]

    if search:
        query += " AND (e.subject LIKE ? OR e.body LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]

    query += " ORDER BY e.created_at DESC"

    rows = await db.execute_fetchall(query, params)
    return [
        EmailResponse(**_row_to_email(
            r,
            sender_username=r["sender_username"],
            sender_display_name=r["sender_display_name"],
        ))
        for r in rows
    ]


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(email_id: int, request: Request, db=Depends(get_raw_db)):
    """Get a single email by ID."""
    user_id = _get_current_user_id(request)

    rows = await db.execute_fetchall(
        """SELECT e.id, e.sender_id, e.recipients, e.cc, e.subject, e.body,
                  e.folder, e.is_read, e.is_starred, e.created_at,
                  u.username AS sender_username,
                  COALESCE(u.display_name, u.username) AS sender_display_name
           FROM emails e
           JOIN users u ON u.id = e.sender_id
           WHERE e.id = ?""",
        (email_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Email not found")

    row = rows[0]

    # Verify access: user must be sender or recipient
    recipients = []
    try:
        recipients = json.loads(row["recipients"]) if row["recipients"] else []
    except (json.JSONDecodeError, TypeError):
        pass

    is_sender = row["sender_id"] == user_id
    is_recipient = str(user_id) in [str(r) for r in recipients]

    if not is_sender and not is_recipient:
        raise HTTPException(status_code=403, detail="Access denied")

    return EmailResponse(**_row_to_email(
        row,
        sender_username=row["sender_username"],
        sender_display_name=row["sender_display_name"],
    ))


@router.post("", response_model=EmailResponse, status_code=201)
async def create_email(body: EmailCreate, request: Request, db=Depends(get_raw_db)):
    """Create/send an email."""
    user_id = _get_current_user_id(request)
    now = datetime.now(timezone.utc).isoformat()

    folder = body.folder if body.folder in VALID_FOLDERS else "drafts"

    # If sending (not draft), also create inbox copies for recipients
    recipients_json = json.dumps(body.recipients)
    cc_json = json.dumps(body.cc)

    cursor = await db.execute(
        """INSERT INTO emails (sender_id, recipients, cc, subject, body, folder, is_read, is_starred, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
        (user_id, recipients_json, cc_json, body.subject, body.body, folder, 1 if folder == "sent" else 0, now),
    )
    email_id = cursor.lastrowid

    # If sending, create inbox copies for each recipient
    if folder == "sent":
        all_recipients = body.recipients + body.cc
        for recipient_id_str in all_recipients:
            try:
                rid = int(recipient_id_str)
            except (ValueError, TypeError):
                continue
            # Verify recipient exists
            user_row = await db.execute_fetchall("SELECT id FROM users WHERE id = ?", (rid,))
            if user_row:
                await db.execute(
                    """INSERT INTO emails (sender_id, recipients, cc, subject, body, folder, is_read, is_starred, created_at)
                       VALUES (?, ?, ?, ?, ?, 'inbox', 0, 0, ?)""",
                    (user_id, json.dumps([str(rid)]), cc_json, body.subject, body.body, now),
                )

    await db.commit()

    # Fetch created email
    rows = await db.execute_fetchall(
        """SELECT e.id, e.sender_id, e.recipients, e.cc, e.subject, e.body,
                  e.folder, e.is_read, e.is_starred, e.created_at,
                  u.username AS sender_username,
                  COALESCE(u.display_name, u.username) AS sender_display_name
           FROM emails e
           JOIN users u ON u.id = e.sender_id
           WHERE e.id = ?""",
        (email_id,),
    )
    row = rows[0]
    return EmailResponse(**_row_to_email(
        row,
        sender_username=row["sender_username"],
        sender_display_name=row["sender_display_name"],
    ))


@router.put("/{email_id}", response_model=EmailResponse)
async def update_email(email_id: int, body: EmailUpdate, request: Request, db=Depends(get_raw_db)):
    """Update email properties (mark as read, move to folder, star)."""
    user_id = _get_current_user_id(request)

    rows = await db.execute_fetchall("SELECT id, sender_id, recipients FROM emails WHERE id = ?", (email_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Email not found")

    updates = []
    params: list = []

    if body.is_read is not None:
        updates.append("is_read = ?")
        params.append(1 if body.is_read else 0)

    if body.is_starred is not None:
        updates.append("is_starred = ?")
        params.append(1 if body.is_starred else 0)

    if body.folder is not None:
        if body.folder not in VALID_FOLDERS:
            raise HTTPException(status_code=400, detail=f"Invalid folder. Must be one of: {', '.join(VALID_FOLDERS)}")
        updates.append("folder = ?")
        params.append(body.folder)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(email_id)
    await db.execute(f"UPDATE emails SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    # Return updated email
    return await get_email(email_id, request, db)


@router.delete("/{email_id}", status_code=204)
async def delete_email(email_id: int, request: Request, db=Depends(get_raw_db)):
    """Move email to trash, or permanently delete if already in trash."""
    user_id = _get_current_user_id(request)

    rows = await db.execute_fetchall(
        "SELECT id, folder, sender_id, recipients FROM emails WHERE id = ?", (email_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Email not found")

    email = rows[0]

    if email["folder"] == "trash":
        # Permanently delete
        await db.execute("DELETE FROM emails WHERE id = ?", (email_id,))
    else:
        # Move to trash
        await db.execute("UPDATE emails SET folder = 'trash' WHERE id = ?", (email_id,))

    await db.commit()
