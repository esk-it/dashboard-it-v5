"""Gmail API service with local SQLite cache (Outlook-style offline).

- First launch: full sync from Gmail to local DB
- Subsequent: incremental sync via Gmail history API
- Read/list: always from local DB (instant)
- Send/star/trash: API call + update local cache
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx

from . import google_calendar as gcal

logger = logging.getLogger(__name__)

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

FOLDER_QUERIES = {
    "inbox": "in:inbox",
    "sent": "in:sent",
    "starred": "is:starred",
    "important": "is:important",
    "trash": "in:trash",
    "draft": "in:drafts",
}

FOLDER_LABELS = {
    "inbox": "INBOX",
    "sent": "SENT",
    "starred": "STARRED",
    "important": "IMPORTANT",
    "trash": "TRASH",
    "draft": "DRAFT",
}


# ═══════════════════════════════════════════════════════════════
# Gmail API helpers (unchanged)
# ═══════════════════════════════════════════════════════════════


async def has_gmail_scope() -> bool:
    try:
        token = await gcal._ensure_valid_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GMAIL_API}/profile", headers={"Authorization": f"Bearer {token}"})
            return resp.status_code == 200
    except Exception:
        return False


def _is_inline(part) -> bool:
    headers = {h["name"].lower(): h["value"] for h in part.get("headers", [])}
    if headers.get("content-id"):
        return True
    if headers.get("content-disposition", "").startswith("inline"):
        return True
    return False


def _parse_body(payload: dict) -> tuple[str, str]:
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
    attachments = []
    def _walk(part):
        filename = part.get("filename", "")
        body = part.get("body", {})
        att_id = body.get("attachmentId", "")
        if filename and att_id and not _is_inline(part):
            attachments.append({
                "filename": filename,
                "mimeType": part.get("mimeType", ""),
                "size": body.get("size", 0),
                "attachmentId": att_id,
            })
        for sub in part.get("parts", []):
            _walk(sub)
    _walk(payload)
    return attachments


def _parse_full_message(data: dict) -> dict:
    """Parse a full Gmail message into a flat dict for the cache."""
    headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
    labels = data.get("labelIds", [])
    body_text, body_html = _parse_body(data.get("payload", {}))
    attachments = _parse_attachments(data.get("payload", {}))
    att_names = [a["filename"] for a in attachments]

    # Determine folder
    folder = "inbox"
    if "SENT" in labels:
        folder = "sent"
    elif "DRAFT" in labels:
        folder = "draft"
    elif "TRASH" in labels:
        folder = "trash"

    return {
        "id": data["id"],
        "thread_id": data.get("threadId", ""),
        "folder": folder,
        "sender": headers.get("from", ""),
        "recipient": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", "(sans objet)"),
        "snippet": data.get("snippet", ""),
        "body_text": body_text,
        "body_html": body_html,
        "date_header": headers.get("date", ""),
        "internal_date": data.get("internalDate", ""),
        "is_unread": 1 if "UNREAD" in labels else 0,
        "is_starred": 1 if "STARRED" in labels else 0,
        "labels": json.dumps(labels),
        "has_attachments": 1 if att_names else 0,
        "attachment_names": json.dumps(att_names),
        "attachments_json": json.dumps(attachments),
        "fetched_full": 1,
    }


# ═══════════════════════════════════════════════════════════════
# Sync state helpers
# ═══════════════════════════════════════════════════════════════


async def _get_sync_state(db, key: str) -> str:
    rows = await db.execute_fetchall("SELECT value FROM email_sync_state WHERE key=?", (key,))
    return rows[0][0] if rows else ""


async def _set_sync_state(db, key: str, value: str):
    await db.execute(
        "INSERT OR REPLACE INTO email_sync_state (key, value) VALUES (?, ?)",
        (key, value),
    )


# ═══════════════════════════════════════════════════════════════
# Full sync (initial)
# ═══════════════════════════════════════════════════════════════


async def sync_full(db, max_messages: int = 200) -> dict:
    """Full sync: fetch all recent messages from Gmail and store in local DB."""
    token = await gcal._ensure_valid_token()
    stats = {"fetched": 0, "stored": 0}

    # Get message IDs
    all_ids = []
    next_page = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(all_ids) < max_messages:
            params = {"maxResults": min(100, max_messages - len(all_ids))}
            if next_page:
                params["pageToken"] = next_page
            resp = await client.get(
                f"{GMAIL_API}/messages",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            all_ids.extend([m["id"] for m in data.get("messages", [])])
            next_page = data.get("nextPageToken")
            if not next_page:
                break

    stats["fetched"] = len(all_ids)

    # Fetch full messages in parallel batches of 10
    batch_size = 10
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i:i + batch_size]
        tasks = [_fetch_and_store(token, mid, db) for mid in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        stats["stored"] += sum(1 for r in results if r is True)

    # Save history ID for incremental sync
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_API}/profile",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                history_id = resp.json().get("historyId", "")
                await _set_sync_state(db, "historyId", str(history_id))
    except Exception:
        pass

    now = datetime.now(timezone.utc).isoformat()
    await _set_sync_state(db, "lastFullSync", now)
    await _set_sync_state(db, "lastSync", now)
    await db.commit()
    return stats


async def _fetch_and_store(token: str, message_id: str, db) -> bool:
    """Fetch a single full message from Gmail and store in cache."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{GMAIL_API}/messages/{message_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "full"},
            )
            if resp.status_code != 200:
                return False
            data = resp.json()

        parsed = _parse_full_message(data)
        now = datetime.now(timezone.utc).isoformat()

        await db.execute(
            """INSERT OR REPLACE INTO emails_cache
               (id, thread_id, folder, sender, recipient, cc, subject, snippet,
                body_text, body_html, date_header, internal_date,
                is_unread, is_starred, labels, has_attachments,
                attachment_names, attachments_json, fetched_full, synced_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                parsed["id"], parsed["thread_id"], parsed["folder"],
                parsed["sender"], parsed["recipient"], parsed["cc"],
                parsed["subject"], parsed["snippet"],
                parsed["body_text"], parsed["body_html"],
                parsed["date_header"], parsed["internal_date"],
                parsed["is_unread"], parsed["is_starred"],
                parsed["labels"], parsed["has_attachments"],
                parsed["attachment_names"], parsed["attachments_json"],
                parsed["fetched_full"], now,
            ),
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to fetch/store message {message_id}: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# Incremental sync (fast)
# ═══════════════════════════════════════════════════════════════


async def sync_incremental(db) -> dict:
    """Incremental sync using Gmail history API."""
    token = await gcal._ensure_valid_token()
    history_id = await _get_sync_state(db, "historyId")
    if not history_id:
        return await sync_full(db)

    stats = {"added": 0, "updated": 0, "deleted": 0}

    try:
        changed_ids = set()
        deleted_ids = set()
        next_page = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params = {
                    "startHistoryId": history_id,
                    "historyTypes": "messageAdded,messageDeleted,labelAdded,labelRemoved",
                }
                if next_page:
                    params["pageToken"] = next_page
                resp = await client.get(
                    f"{GMAIL_API}/history",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                if resp.status_code == 404:
                    # History expired — full sync needed
                    return await sync_full(db)
                if resp.status_code != 200:
                    break
                data = resp.json()

                for h in data.get("history", []):
                    for m in h.get("messagesAdded", []):
                        changed_ids.add(m["message"]["id"])
                    for m in h.get("messagesDeleted", []):
                        deleted_ids.add(m["message"]["id"])
                    for m in h.get("labelsAdded", []):
                        changed_ids.add(m["message"]["id"])
                    for m in h.get("labelsRemoved", []):
                        changed_ids.add(m["message"]["id"])

                new_history = data.get("historyId", history_id)
                next_page = data.get("nextPageToken")
                if not next_page:
                    break

        # Delete removed messages
        for mid in deleted_ids:
            await db.execute("DELETE FROM emails_cache WHERE id=?", (mid,))
            stats["deleted"] += 1

        # Fetch changed messages
        changed_ids -= deleted_ids
        batch_size = 10
        id_list = list(changed_ids)
        for i in range(0, len(id_list), batch_size):
            batch = id_list[i:i + batch_size]
            tasks = [_fetch_and_store(token, mid, db) for mid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            stats["added"] += sum(1 for r in results if r is True)

        await _set_sync_state(db, "historyId", str(new_history))
        now = datetime.now(timezone.utc).isoformat()
        await _set_sync_state(db, "lastSync", now)
        await db.commit()

    except Exception as e:
        logger.error(f"Incremental sync failed: {e}")
        # Fall back to full sync
        return await sync_full(db)

    return stats


# ═══════════════════════════════════════════════════════════════
# Local DB reads (instant)
# ═══════════════════════════════════════════════════════════════


async def list_messages_local(db, folder: str = "inbox", query: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    """List messages from local cache — instant."""
    label = FOLDER_LABELS.get(folder, "INBOX")
    if folder == "starred":
        where = "is_starred = 1"
    elif folder == "trash":
        where = "labels LIKE '%TRASH%'"
    elif query:
        where = f"(subject LIKE '%{query}%' OR sender LIKE '%{query}%' OR snippet LIKE '%{query}%')"
    else:
        where = f"labels LIKE '%{label}%'"

    rows = await db.execute_fetchall(
        f"""SELECT id, thread_id, sender, recipient, subject, snippet,
                   date_header, internal_date, is_unread, is_starred,
                   has_attachments, attachment_names
            FROM emails_cache
            WHERE {where}
            ORDER BY CAST(internal_date AS INTEGER) DESC
            LIMIT ? OFFSET ?""",
        (limit, offset),
    )

    return [
        {
            "id": r[0], "threadId": r[1], "from": r[2], "to": r[3],
            "subject": r[4], "snippet": r[5], "date": r[6],
            "internalDate": r[7], "unread": bool(r[8]), "starred": bool(r[9]),
            "hasAttachments": bool(r[10]),
            "attachmentNames": json.loads(r[11]) if r[11] else [],
        }
        for r in rows
    ]


async def get_message_local(db, message_id: str) -> dict | None:
    """Get full message from local cache."""
    rows = await db.execute_fetchall(
        """SELECT id, thread_id, sender, recipient, cc, subject, snippet,
                  body_text, body_html, date_header, internal_date,
                  is_unread, is_starred, labels, has_attachments,
                  attachment_names, attachments_json, fetched_full
           FROM emails_cache WHERE id=?""",
        (message_id,),
    )
    if not rows:
        return None
    r = rows[0]

    # If not fetched full yet, fetch now and update cache
    if not r[17]:
        try:
            token = await gcal._ensure_valid_token()
            await _fetch_and_store(token, message_id, db)
            await db.commit()
            return await get_message_local(db, message_id)
        except Exception:
            pass

    return {
        "id": r[0], "threadId": r[1], "from": r[2], "to": r[3], "cc": r[4],
        "subject": r[5], "snippet": r[6],
        "body_text": r[7], "body_html": r[8],
        "date": r[9], "internalDate": r[10],
        "unread": bool(r[11]), "starred": bool(r[12]),
        "labels": json.loads(r[13]) if r[13] else [],
        "hasAttachments": bool(r[14]),
        "attachmentNames": json.loads(r[15]) if r[15] else [],
        "attachments": json.loads(r[16]) if r[16] else [],
    }


async def get_unread_count_local(db) -> int:
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) FROM emails_cache WHERE is_unread=1 AND labels LIKE '%INBOX%'"
    )
    return rows[0][0] if rows else 0


async def get_sync_status(db) -> dict:
    last_sync = await _get_sync_state(db, "lastSync")
    last_full = await _get_sync_state(db, "lastFullSync")
    count = await db.execute_fetchall("SELECT COUNT(*) FROM emails_cache")
    return {
        "lastSync": last_sync,
        "lastFullSync": last_full,
        "cachedMessages": count[0][0] if count else 0,
    }


# ═══════════════════════════════════════════════════════════════
# Write operations (API + update local cache)
# ═══════════════════════════════════════════════════════════════


async def star_message(db, message_id: str, starred: bool):
    token = await gcal._ensure_valid_token()
    body = {"addLabelIds": ["STARRED"]} if starred else {"removeLabelIds": ["STARRED"]}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/{message_id}/modify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
    # Update local cache
    await db.execute("UPDATE emails_cache SET is_starred=? WHERE id=?", (1 if starred else 0, message_id))
    await db.commit()


async def mark_read(db, message_id: str):
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/{message_id}/modify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"removeLabelIds": ["UNREAD"]},
        )
        resp.raise_for_status()
    await db.execute("UPDATE emails_cache SET is_unread=0 WHERE id=?", (message_id,))
    await db.commit()


async def trash_message(db, message_id: str):
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/{message_id}/trash",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    await db.execute("DELETE FROM emails_cache WHERE id=?", (message_id,))
    await db.commit()


async def get_attachment(message_id: str, attachment_id: str) -> bytes:
    if not attachment_id:
        raise ValueError("No attachment ID")
    token = await gcal._ensure_valid_token()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{GMAIL_API}/messages/{message_id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    data = resp.json().get("data", "")
    return base64.urlsafe_b64decode(data + "==")


async def send_message(to, subject, body, cc="", bcc="", reply_to_message_id=None):
    token = await gcal._ensure_valid_token()
    cfg = gcal.load_config()
    sender = cfg.get("connected_email", "")
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    if cc: msg["Cc"] = cc
    if bcc: msg["Bcc"] = bcc
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(f"<div style='white-space:pre-wrap'>{body}</div>", "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    payload = {"raw": raw}
    if reply_to_message_id:
        payload["threadId"] = reply_to_message_id  # simplified
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()


async def send_message_with_attachments(to, subject, body, cc="", bcc="", reply_to_message_id=None, attachments=None):
    token = await gcal._ensure_valid_token()
    cfg = gcal.load_config()
    sender = cfg.get("connected_email", "")
    from email.mime.base import MIMEBase
    from email import encoders
    msg = MIMEMultipart("mixed")
    msg["To"] = to
    msg["From"] = sender
    msg["Subject"] = subject
    if cc: msg["Cc"] = cc
    if bcc: msg["Bcc"] = bcc
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body, "plain"))
    body_part.attach(MIMEText(f"<div style='white-space:pre-wrap'>{body}</div>", "html"))
    msg.attach(body_part)
    if attachments:
        for filename, mime_type, data in attachments:
            maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    payload = {"raw": raw}
    if reply_to_message_id:
        payload["threadId"] = reply_to_message_id
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_API}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()


async def get_signature() -> str:
    token = await gcal._ensure_valid_token()
    cfg = gcal.load_config()
    email = cfg.get("connected_email", "")

    # If email is empty, fetch from Gmail profile
    if not email:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{GMAIL_API}/profile",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    email = resp.json().get("emailAddress", "")
                    if email:
                        gcal.save_config({"connected_email": email})
        except Exception:
            pass

    if not email:
        return ""

    try:
        async with httpx.AsyncClient() as client:
            # Try sendAs endpoint
            resp = await client.get(
                f"{GMAIL_API}/settings/sendAs/{email}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                html_sig = resp.json().get("signature", "")
                return re.sub(r'<[^>]+>', '', html_sig).strip()

            # If sendAs fails, try listing all sendAs to find the primary
            resp = await client.get(
                f"{GMAIL_API}/settings/sendAs",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                for sa in resp.json().get("sendAs", []):
                    if sa.get("isPrimary"):
                        html_sig = sa.get("signature", "")
                        return re.sub(r'<[^>]+>', '', html_sig).strip()
    except Exception as e:
        logger.warning(f"Failed to fetch signature: {e}")
    return ""
