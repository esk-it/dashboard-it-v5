from __future__ import annotations

from pydantic import BaseModel, ConfigDict


# --------------- Request schemas ---------------

class EmailCreate(BaseModel):
    recipients: list[str] = []
    cc: list[str] = []
    subject: str = ""
    body: str = ""
    folder: str = "drafts"


class EmailUpdate(BaseModel):
    is_read: bool | None = None
    is_starred: bool | None = None
    folder: str | None = None


# --------------- Response schemas ---------------

class EmailResponse(BaseModel):
    id: int
    sender_id: int
    sender_username: str = ""
    sender_display_name: str = ""
    recipients: list[str] = []
    cc: list[str] = []
    subject: str
    body: str
    folder: str
    is_read: bool
    is_starred: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class FolderCountResponse(BaseModel):
    folder: str
    count: int
    unread: int
