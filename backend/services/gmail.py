"""Gmail API service — uses shared Google OAuth from google_calendar.py."""
from __future__ import annotations

import asyncio
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx

from . import google_calendar as gcal

logger = logging.getLogger(__name__)

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

# Folder → Gmail query mapping
FOLDER_QUERIES = {
    "inbox": "in:inbox",
    "sent": "in:sent",
    "starred": "is:starred",
    "important": "is:important",
    "trash": "in:trash",
    "draft": "in:drafts",
}


async def has_gmail_scope() -> bool:
    """Check if the current token has Gmail access."""
    try:
        token = await gcal._ensure_valid_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_API}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


# ── List messages ────────────────────────────────────────────


async def list_messages(
    folder: str = "inbox",
    query: str = "",
    max_results: int = 50,
    page_token: str | None = None,
) -> dict:
    """List messages with metadata (sender, subject, snippet, date)."""
    token = await gcal._ensure_valid_token()

    # Build query
    q = FOLDER_QUERIES.get(folder, f"in:{folder}")
    if query:
        q += f" {query}"

    params: dict = {"q": q, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    message_ids = [m["id"] for m in data.get("messages", [])]
    next_page = data.get("nextPageToken")
    result_size = data.get("resultSizeEstimate", 0)

    if not message_ids:
        return {"messages": [], "nextPageToken": None, "resultSizeEstimate": 0}

    # Fetch metadata for each message in parallel (batched)
    messages = await _fetch_messages_metadata(token, message_ids)

    return {
        "messages": messages,
        "nextPageToken": next_page,
        "resultSizeEstimate": result_size,
    }


async def _fetch_messages_metadata(token: str, ids: list[str]) -> list[dict]:
    """Fetch message metadata in parallel, batched to 10 concurrent."""
    results = []
    batch_size = 10

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        tasks = [_get_message_metadata(token, mid) for mid in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in batch_results:
            if isinstance(r, dict):
                results.append(r)

    return results


async def _get_message_metadata(token: str, message_id: str) -> dict:
    """Get message metadata (headers, snippet, labels)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            params=[
                ("format", "metadata"),
                ("metadataHeaders", "From"),
                ("metadataHeaders", "To"),
                ("metadataHeaders", "Subject"),
                ("metadataHeaders", "Date"),
            ],
        )
        resp.raise_for_status()
        data = resp.json()

    headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
    labels = data.get("labelIds", [])

    # Check for real attachments (not inline images)
    def _has_real_attachments(part):
        headers = {h["name"].lower(): h["value"] for h in part.get("headers", [])}
        filename = part.get("filename", "")
        if filename and part.get("body", {}).get("attachmentId"):
            if not headers.get("content-id") and not headers.get("content-disposition", "").startswith("inline"):
                return True
        for sub in part.get("parts", []):
            if _has_real_attachments(sub):
                return True
        return False
    has_attachments = _has_real_attachments(data.get("payload", {}))

    return {
        "id": data["id"],
        "threadId": data.get("threadId", ""),
        "snippet": data.get("snippet", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "(sans objet)"),
        "date": headers.get("date", ""),
        "internalDate": data.get("internalDate", ""),
        "unread": "UNREAD" in labels,
        "starred": "STARRED" in labels,
        "labels": labels,
        "hasAttachments": has_attachments,
    }


# ── Get full message ─────────────────────────────────────────


async def get_message(message_id: str) -> dict:
    """Get full message content (headers + body)."""
    token = await gcal._ensure_valid_token()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/messages/{message_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={"format": "full"},
        )
        resp.raise_for_status()
        data = resp.json()

    headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
    labels = data.get("labelIds", [])

    # Parse body
    body_text, body_html = _parse_body(data.get("payload", {}))

    # Attachments
    attachments = _parse_attachments(data.get("payload", {}))

    return {
        "id": data["id"],
        "threadId": data.get("threadId", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", "(sans objet)"),
        "date": headers.get("date", ""),
        "internalDate": data.get("internalDate", ""),
        "unread": "UNREAD" in labels,
        "starred": "STARRED" in labels,
        "labels": labels,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
    }


def _parse_body(payload: dict) -> tuple[str, str]:
    """Recursively parse MIME parts to extract text/plain and text/html."""
    text = ""
    html = ""
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif "multipart" in mime:
        for part in payload.get("parts", []):
            t, h = _parse_body(part)
            if t and not text:
                text = t
            if h and not html:
                html = h

    return text, html


def _parse_attachments(payload: dict) -> list[dict]:
    """Extract real attachments only (excludes inline images like signature logos)."""
    attachments = []

    def _is_inline(part) -> bool:
        """Check if a part is an inline image (signature logo, etc.)."""
        headers = {h["name"].lower(): h["value"] for h in part.get("headers", [])}
        # Has Content-ID = inline image referenced in HTML
        if headers.get("content-id"):
            return True
        # Content-Disposition starts with "inline"
        disp = headers.get("content-disposition", "")
        if disp.startswith("inline"):
            return True
        return False

    def _walk(part):
        mime = part.get("mimeType", "")
        filename = part.get("filename", "")
        body = part.get("body", {})
        att_id = body.get("attachmentId", "")

        if filename and att_id and not _is_inline(part):
            attachments.append({
                "filename": filename,
                "mimeType": mime,
                "size": body.get("size", 0),
                "attachmentId": att_id,
            })

        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)
    return attachments


# ── Send message ─────────────────────────────────────────────


async def get_attachment(message_id: str, attachment_id: str) -> bytes:
    """Download an attachment by ID."""
    if not attachment_id:
        raise ValueError("No attachment ID — inline attachment cannot be downloaded separately")
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{GMAIL_API}/messages/{message_id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    data = resp.json().get("data", "")
    return base64.urlsafe_b64decode(data + "==")


async def send_message_with_attachments(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    reply_to_message_id: str | None = None,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> dict:
    """Send an email with optional attachments. attachments = [(filename, mime, data), ...]"""
    token = await gcal._ensure_valid_token()
    cfg = gcal.load_config()
    sender = cfg.get("connected_email", "")

    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart("mixed")
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    # Body
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body, "plain"))
    body_part.attach(MIMEText(f"<div style='white-space:pre-wrap'>{body}</div>", "html"))
    msg.attach(body_part)

    # Attachments
    if attachments:
        for filename, mime_type, data in attachments:
            maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    payload: dict = {"raw": raw}

    if reply_to_message_id:
        try:
            orig = await get_message(reply_to_message_id)
            payload["threadId"] = orig.get("threadId", "")
        except Exception:
            pass

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()


async def send_message(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    reply_to_message_id: str | None = None,
) -> dict:
    """Send an email via Gmail API."""
    token = await gcal._ensure_valid_token()
    cfg = gcal.load_config()
    sender = cfg.get("connected_email", "")

    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    # Add plain text + HTML
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(f"<div>{body}</div>", "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    payload: dict = {"raw": raw}
    if reply_to_message_id:
        # Get thread ID for reply
        try:
            orig = await get_message(reply_to_message_id)
            payload["threadId"] = orig.get("threadId", "")
        except Exception:
            pass

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()


# ── Label operations ─────────────────────────────────────────


async def modify_labels(message_id: str, add: list[str] = None, remove: list[str] = None) -> dict:
    """Add or remove labels from a message."""
    token = await gcal._ensure_valid_token()
    body = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/{message_id}/modify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
    return resp.json()


async def star_message(message_id: str, starred: bool) -> dict:
    """Toggle star on a message."""
    if starred:
        return await modify_labels(message_id, add=["STARRED"])
    else:
        return await modify_labels(message_id, remove=["STARRED"])


async def mark_read(message_id: str) -> dict:
    """Mark a message as read."""
    return await modify_labels(message_id, remove=["UNREAD"])


async def trash_message(message_id: str) -> dict:
    """Move a message to trash."""
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/{message_id}/trash",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    return resp.json()


# ── Labels ───────────────────────────────────────────────────


async def list_labels() -> list[dict]:
    """List all Gmail labels."""
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/labels",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()

    labels = resp.json().get("labels", [])
    return [
        {
            "id": l["id"],
            "name": l.get("name", ""),
            "type": l.get("type", ""),
            "messagesTotal": l.get("messagesTotal", 0),
            "messagesUnread": l.get("messagesUnread", 0),
        }
        for l in labels
    ]


async def get_signature() -> str:
    """Get the user's Gmail signature from the primary sendAs alias."""
    token = await gcal._ensure_valid_token()
    cfg = gcal.load_config()
    email = cfg.get("connected_email", "me")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_API}/settings/sendAs/{email}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                html_sig = resp.json().get("signature", "")
                # Strip HTML tags for plain text version
                import re
                text_sig = re.sub(r'<[^>]+>', '', html_sig).strip()
                return text_sig
    except Exception as e:
        logger.warning(f"Failed to fetch Gmail signature: {e}")
    return ""


async def get_unread_count() -> int:
    """Get inbox unread count."""
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API}/labels/INBOX",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return 0
    return resp.json().get("messagesUnread", 0)
