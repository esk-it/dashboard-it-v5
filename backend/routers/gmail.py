"""Gmail API endpoints — reads from local SQLite cache, syncs with Gmail."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from ..database import get_raw_db
from ..services import gmail
from ..services import google_calendar as gcal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gmail", tags=["gmail"])


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""
    reply_to_message_id: str | None = None
    signature_html: str = ""


def _check_connected():
    if not gcal.is_connected():
        raise HTTPException(status_code=403, detail="Google not connected")


@router.get("/status")
async def status(db=Depends(get_raw_db)):
    if not gcal.is_connected():
        return {"connected": False, "has_scope": False, "email": ""}
    has_scope = await gmail.has_gmail_scope()
    cfg = gcal.load_config()
    sync_status = await gmail.get_sync_status(db)
    return {
        "connected": True,
        "has_scope": has_scope,
        "email": cfg.get("connected_email", "") if cfg else "",
        **sync_status,
    }


@router.post("/sync")
async def sync(db=Depends(get_raw_db)):
    """Trigger sync — incremental if possible, full otherwise."""
    _check_connected()
    try:
        stats = await gmail.sync_incremental(db)
        return {"ok": True, **stats}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/sync/full")
async def sync_full(db=Depends(get_raw_db)):
    """Force a full sync from Gmail."""
    _check_connected()
    try:
        stats = await gmail.sync_full(db)
        return {"ok": True, **stats}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/messages")
async def list_messages(
    folder: str = "inbox",
    q: str = "",
    max_results: int = 50,
    offset: int = 0,
    db=Depends(get_raw_db),
):
    """List messages from local cache — instant."""
    _check_connected()
    messages = await gmail.list_messages_local(db, folder=folder, query=q, limit=max_results, offset=offset)
    return {"messages": messages}


@router.get("/messages/{message_id}")
async def get_message(message_id: str, db=Depends(get_raw_db)):
    """Get full message from local cache."""
    _check_connected()
    msg = await gmail.get_message_local(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found in cache")
    return msg


@router.post("/send")
async def send_email(body: SendEmailRequest):
    _check_connected()
    try:
        result = await gmail.send_message(
            to=body.to, subject=body.subject, body=body.body,
            cc=body.cc, bcc=body.bcc,
            reply_to_message_id=body.reply_to_message_id,
            signature_html=body.signature_html,
        )
        return {"sent": True, "id": result.get("id", "")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/send-with-attachments")
async def send_with_attachments(
    to: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    cc: str = Form(""),
    bcc: str = Form(""),
    reply_to_message_id: str = Form(""),
    signature_html: str = Form(""),
    files: List[UploadFile] = File(default=[]),
):
    _check_connected()
    try:
        attachments = []
        for f in files:
            content = await f.read()
            attachments.append((f.filename, f.content_type or "application/octet-stream", content))
        result = await gmail.send_message_with_attachments(
            to=to, subject=subject, body=body, cc=cc, bcc=bcc,
            reply_to_message_id=reply_to_message_id or None,
            attachments=attachments if attachments else None,
            signature_html=signature_html,
        )
        return {"sent": True, "id": result.get("id", "")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/messages/{message_id}/attachments/{attachment_id}")
async def download_attachment(message_id: str, attachment_id: str, filename: str = "attachment"):
    _check_connected()
    try:
        data = await gmail.get_attachment(message_id, attachment_id)
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/messages/{message_id}/star")
async def toggle_star(message_id: str, starred: bool = True, db=Depends(get_raw_db)):
    _check_connected()
    try:
        await gmail.star_message(db, message_id, starred)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/messages/{message_id}/trash")
async def trash(message_id: str, db=Depends(get_raw_db)):
    _check_connected()
    try:
        await gmail.trash_message(db, message_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/messages/{message_id}/read")
async def mark_as_read(message_id: str, db=Depends(get_raw_db)):
    _check_connected()
    try:
        await gmail.mark_read(db, message_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/signature")
async def get_signature():
    _check_connected()
    try:
        sig = await gmail.get_signature()
        return {"signature": sig}
    except Exception:
        return {"signature": ""}


@router.get("/unread-count")
async def unread_count(db=Depends(get_raw_db)):
    try:
        count = await gmail.get_unread_count_local(db)
        return {"count": count}
    except Exception:
        return {"count": 0}
