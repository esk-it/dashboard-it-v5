from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    title: str
    doc_type: str = ""
    supplier_id: int | None = None
    supplier: str | None = None  # Free-text supplier name; backend resolves to supplier_id if match found
    doc_date: str | None = None
    reference: str = ""
    file_path: str = ""
    file_hash: str = ""
    notes: str = ""
    tag_ids: list[int] = []
    is_acompte: bool = False  # only meaningful for FACTURE — marks a partial / down-payment invoice


class DocumentUpdate(DocumentCreate):
    pass


class DocumentResponse(BaseModel):
    id: int
    title: str
    doc_type: str
    supplier_id: int | None
    supplier_name: str
    doc_date: str | None
    reference: str           # external reference (printed on the supplier's PDF, optional)
    internal_ref: str = ""   # our auto-generated identifier (DEV-2026-001, FAC-2026-042, …)
    file_path: str
    file_hash: str
    notes: str
    created_at: str
    tags: str = ""           # CSV string of tag names — present on the list endpoint, used by the UI for filter + display
    is_acompte: bool = False # only meaningful when doc_type == FACTURE

    model_config = ConfigDict(from_attributes=True)


class TagResponse(BaseModel):
    id: int
    name: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class DocumentLinkResponse(BaseModel):
    id: int
    source_id: int
    target_id: int
    link_type: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class DocumentLinkCreate(BaseModel):
    target_id: int
    link_type: str = "related"


class DocumentDetailResponse(DocumentResponse):
    tags: list[TagResponse] = []
    links: list[DocumentLinkResponse] = []
