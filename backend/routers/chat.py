"""Internal chat/messaging system router."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..database import get_raw_db
from ..schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    ParticipantResponse,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])

SECRET_KEY = os.environ.get("ITMANAGER_JWT_SECRET", "itmanager-dev-secret-key-change-me")
ALGORITHM = "HS256"


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


async def _build_conversation_response(db, conv_row, current_user_id: int) -> dict:
    """Build a full conversation response dict with participants and last message."""
    conv_id = conv_row["id"]

    # Fetch participants with user info
    participants_rows = await db.execute_fetchall(
        """SELECT cp.id, cp.conversation_id, cp.user_id, cp.joined_at,
                  u.username, COALESCE(u.display_name, u.username) AS display_name
           FROM chat_participants cp
           JOIN users u ON u.id = cp.user_id
           WHERE cp.conversation_id = ?
           ORDER BY cp.joined_at ASC""",
        (conv_id,),
    )
    participants = [
        {
            "id": p["id"],
            "conversation_id": p["conversation_id"],
            "user_id": p["user_id"],
            "username": p["username"],
            "display_name": p["display_name"],
            "joined_at": p["joined_at"],
        }
        for p in participants_rows
    ]

    # Fetch last message
    last_msg_row = await db.execute_fetchall(
        """SELECT m.id, m.conversation_id, m.sender_id, m.content, m.created_at, m.is_read,
                  u.username AS sender_username,
                  COALESCE(u.display_name, u.username) AS sender_display_name
           FROM chat_messages m
           JOIN users u ON u.id = m.sender_id
           WHERE m.conversation_id = ?
           ORDER BY m.created_at DESC LIMIT 1""",
        (conv_id,),
    )
    last_message = None
    if last_msg_row:
        lm = last_msg_row[0]
        last_message = {
            "id": lm["id"],
            "conversation_id": lm["conversation_id"],
            "sender_id": lm["sender_id"],
            "sender_username": lm["sender_username"],
            "sender_display_name": lm["sender_display_name"],
            "content": lm["content"],
            "created_at": lm["created_at"],
            "is_read": bool(lm["is_read"]),
        }

    # Unread count for current user
    unread_row = await db.execute_fetchall(
        """SELECT COUNT(*) FROM chat_messages
           WHERE conversation_id = ? AND sender_id != ? AND is_read = 0""",
        (conv_id, current_user_id),
    )
    unread_count = unread_row[0][0] if unread_row else 0

    return {
        "id": conv_row["id"],
        "title": conv_row["title"] or "",
        "created_at": conv_row["created_at"],
        "updated_at": conv_row["updated_at"],
        "participants": participants,
        "last_message": last_message,
        "unread_count": unread_count,
    }


# --------------- Routes ---------------

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(request: Request, db=Depends(get_raw_db)):
    """List all conversations for the current user."""
    user_id = _get_current_user_id(request)

    rows = await db.execute_fetchall(
        """SELECT c.id, c.title, c.created_at, c.updated_at
           FROM chat_conversations c
           JOIN chat_participants cp ON cp.conversation_id = c.id
           WHERE cp.user_id = ?
           ORDER BY c.updated_at DESC""",
        (user_id,),
    )

    results = []
    for row in rows:
        conv = await _build_conversation_response(db, row, user_id)
        results.append(ConversationResponse(**conv))
    return results


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(body: ConversationCreate, request: Request, db=Depends(get_raw_db)):
    """Create a new conversation with participants."""
    user_id = _get_current_user_id(request)
    now = datetime.now(timezone.utc).isoformat()

    cursor = await db.execute(
        "INSERT INTO chat_conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
        (body.title, now, now),
    )
    conv_id = cursor.lastrowid

    # Add the creator as a participant
    await db.execute(
        "INSERT INTO chat_participants (conversation_id, user_id, joined_at) VALUES (?, ?, ?)",
        (conv_id, user_id, now),
    )

    # Add other participants
    for pid in body.participant_ids:
        if pid == user_id:
            continue
        # Verify user exists
        user_row = await db.execute_fetchall("SELECT id FROM users WHERE id = ?", (pid,))
        if not user_row:
            await db.execute("DELETE FROM chat_participants WHERE conversation_id = ?", (conv_id,))
            await db.execute("DELETE FROM chat_conversations WHERE id = ?", (conv_id,))
            await db.commit()
            raise HTTPException(status_code=404, detail=f"User {pid} not found")
        await db.execute(
            "INSERT INTO chat_participants (conversation_id, user_id, joined_at) VALUES (?, ?, ?)",
            (conv_id, pid, now),
        )

    await db.commit()

    # Re-fetch conversation
    conv_rows = await db.execute_fetchall(
        "SELECT id, title, created_at, updated_at FROM chat_conversations WHERE id = ?",
        (conv_id,),
    )
    conv = await _build_conversation_response(db, conv_rows[0], user_id)
    return ConversationResponse(**conv)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(conversation_id: int, request: Request, db=Depends(get_raw_db)):
    """Get messages in a conversation."""
    user_id = _get_current_user_id(request)

    # Verify the user is a participant
    participant = await db.execute_fetchall(
        "SELECT id FROM chat_participants WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, user_id),
    )
    if not participant:
        raise HTTPException(status_code=403, detail="You are not a participant in this conversation")

    rows = await db.execute_fetchall(
        """SELECT m.id, m.conversation_id, m.sender_id, m.content, m.created_at, m.is_read,
                  u.username AS sender_username,
                  COALESCE(u.display_name, u.username) AS sender_display_name
           FROM chat_messages m
           JOIN users u ON u.id = m.sender_id
           WHERE m.conversation_id = ?
           ORDER BY m.created_at ASC""",
        (conversation_id,),
    )

    # Mark messages as read for this user
    await db.execute(
        "UPDATE chat_messages SET is_read = 1 WHERE conversation_id = ? AND sender_id != ?",
        (conversation_id, user_id),
    )
    await db.commit()

    return [
        MessageResponse(
            id=r["id"],
            conversation_id=r["conversation_id"],
            sender_id=r["sender_id"],
            sender_username=r["sender_username"],
            sender_display_name=r["sender_display_name"],
            content=r["content"],
            created_at=r["created_at"],
            is_read=True,  # We just marked them as read
        )
        for r in rows
    ]


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def send_message(conversation_id: int, body: MessageCreate, request: Request, db=Depends(get_raw_db)):
    """Send a message in a conversation."""
    user_id = _get_current_user_id(request)

    # Verify conversation exists
    conv_rows = await db.execute_fetchall(
        "SELECT id FROM chat_conversations WHERE id = ?", (conversation_id,),
    )
    if not conv_rows:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify the user is a participant
    participant = await db.execute_fetchall(
        "SELECT id FROM chat_participants WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, user_id),
    )
    if not participant:
        raise HTTPException(status_code=403, detail="You are not a participant in this conversation")

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    now = datetime.now(timezone.utc).isoformat()

    cursor = await db.execute(
        """INSERT INTO chat_messages (conversation_id, sender_id, content, created_at, is_read)
           VALUES (?, ?, ?, ?, 0)""",
        (conversation_id, user_id, body.content, now),
    )
    msg_id = cursor.lastrowid

    # Update conversation updated_at
    await db.execute(
        "UPDATE chat_conversations SET updated_at = ? WHERE id = ?",
        (now, conversation_id),
    )
    await db.commit()

    # Fetch sender info
    sender_rows = await db.execute_fetchall(
        "SELECT username, COALESCE(display_name, username) AS display_name FROM users WHERE id = ?",
        (user_id,),
    )
    sender = sender_rows[0] if sender_rows else None

    return MessageResponse(
        id=msg_id,
        conversation_id=conversation_id,
        sender_id=user_id,
        sender_username=sender["username"] if sender else "",
        sender_display_name=sender["display_name"] if sender else "",
        content=body.content,
        created_at=now,
        is_read=False,
    )


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: int, request: Request, db=Depends(get_raw_db)):
    """Delete a message. Only the sender can delete their own messages."""
    user_id = _get_current_user_id(request)

    rows = await db.execute_fetchall(
        "SELECT id, sender_id FROM chat_messages WHERE id = ?", (message_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Message not found")

    if rows[0]["sender_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")

    await db.execute("DELETE FROM chat_messages WHERE id = ?", (message_id,))
    await db.commit()
