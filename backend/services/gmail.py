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
    """Extract attachment info from MIME parts."""
    attachments = []
    mime = payload.get("mimeType", "")

    if "multipart" in mime:
        for part in payload.get("parts", []):
            filename = part.get("filename", "")
            if filename:
                attachments.append({
                    "filename": filename,
                    "mimeType": part.get("mimeType", ""),
                    "size": part.get("body", {}).get("size", 0),
                    "attachmentId": part.get("body", {}).get("attachmentId", ""),
                })
            # Recurse
            attachments.extend(_parse_attachments(part))

    return attachments


# ── Send message ─────────────────────────────────────────────


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
