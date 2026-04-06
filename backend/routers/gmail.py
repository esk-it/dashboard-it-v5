"""Gmail API endpoints."""
from __future__ import annotations

import base64
import logging
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

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


def _check_connected():
    if not gcal.is_connected():
        raise HTTPException(status_code=403, detail="Google not connected")


@router.get("/status")
async def status():
    """Check Gmail connection status."""
    if not gcal.is_connected():
        return {"connected": False, "has_scope": False, "email": ""}
    has_scope = await gmail.has_gmail_scope()
    cfg = gcal.load_config()
    return {
        "connected": True,
        "has_scope": has_scope,
        "email": cfg.get("connected_email", "") if cfg else "",
    }


@router.get("/messages")
async def list_messages(
    folder: str = "inbox",
    q: str = "",
    max_results: int = 50,
    page_token: str = "",
):
    """List messages in a folder."""
    _check_connected()
    try:
        return await gmail.list_messages(
            folder=folder,
            query=q,
            max_results=max_results,
            page_token=page_token or None,
        )
    except Exception as e:
        logger.error(f"Gmail list_messages error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/messages/{message_id}")
async def get_message(message_id: str):
    """Get full message content."""
    _check_connected()
    try:
        return await gmail.get_message(message_id)
    except Exception as e:
        logger.error(f"Gmail get_message error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/send")
async def send_email(body: SendEmailRequest):
    """Send an email."""
    _check_connected()
    try:
        result = await gmail.send_message(
            to=body.to,
            subject=body.subject,
            body=body.body,
            cc=body.cc,
            bcc=body.bcc,
            reply_to_message_id=body.reply_to_message_id,
        )
        return {"sent": True, "id": result.get("id", "")}
    except Exception as e:
        logger.error(f"Gmail send error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/messages/{message_id}/star")
async def toggle_star(message_id: str, starred: bool = True):
    """Toggle star on a message."""
    _check_connected()
    try:
        await gmail.star_message(message_id, starred)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/messages/{message_id}/trash")
async def trash(message_id: str):
    """Move message to trash."""
    _check_connected()
    try:
        await gmail.trash_message(message_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/messages/{message_id}/read")
async def mark_as_read(message_id: str):
    """Mark message as read."""
    _check_connected()
    try:
        await gmail.mark_read(message_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/messages/{message_id}/attachments/{attachment_id}")
async def download_attachment(message_id: str, attachment_id: str, filename: str = "attachment"):
    """Download an attachment."""
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


@router.post("/send-with-attachments")
async def send_with_attachments(
    to: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    cc: str = Form(""),
    bcc: str = Form(""),
    reply_to_message_id: str = Form(""),
    files: List[UploadFile] = File(default=[]),
):
    """Send an email with file attachments."""
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
        )
        return {"sent": True, "id": result.get("id", "")}
    except Exception as e:
        logger.error(f"Gmail send with attachments error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/signature")
async def get_signature():
    """Get Gmail signature."""
    _check_connected()
    try:
        sig = await gmail.get_signature()
        return {"signature": sig}
    except Exception:
        return {"signature": ""}


@router.get("/labels")
async def labels():
    """List all Gmail labels."""
    _check_connected()
    try:
        return {"labels": await gmail.list_labels()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/unread-count")
async def unread_count():
    """Get inbox unread count."""
    try:
        count = await gmail.get_unread_count()
        return {"count": count}
    except Exception:
        return {"count": 0}
