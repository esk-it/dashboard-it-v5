from __future__ import annotations

from pydantic import BaseModel, ConfigDict


# --------------- Request schemas ---------------

class ConversationCreate(BaseModel):
    title: str = ""
    participant_ids: list[int] = []


class MessageCreate(BaseModel):
    content: str


# --------------- Response schemas ---------------

class ParticipantResponse(BaseModel):
    id: int
    conversation_id: int
    user_id: int
    username: str = ""
    display_name: str = ""
    joined_at: str

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_username: str = ""
    sender_display_name: str = ""
    content: str
    created_at: str
    is_read: bool

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    participants: list[ParticipantResponse] = []
    last_message: MessageResponse | None = None
    unread_count: int = 0

    model_config = ConfigDict(from_attributes=True)
