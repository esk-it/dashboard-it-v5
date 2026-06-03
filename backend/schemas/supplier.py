from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SupplierContact(BaseModel):
    name: str = ""
    role: str = ""
    phone: str = ""
    email: str = ""


class SupplierCreate(BaseModel):
    name: str
    domain: str = ""
    phone: str = ""
    email: str = ""
    contact: str = ""
    notes: str = ""
    contacts: list[SupplierContact] = []


class SupplierUpdate(SupplierCreate):
    pass


class TimelineEvent(BaseModel):
    """One row in the supplier's chronological activity feed (v7.1.0)."""
    kind: str          # 'dossier_created' | 'doc_added' | 'status' | 'note' | 'delivery'
    body: str = ""
    created_at: str
    dossier_id: int | None = None
    dossier_title: str = ""
    icon: str = ""     # emoji hint for the UI


class ServiceCount(BaseModel):
    """Aggregate of doc-type usage for the supplier's 'catalog' display."""
    doc_type: str
    count: int


class SupplierResponse(BaseModel):
    id: int
    name: str
    domain: str
    phone: str
    email: str
    contact: str
    notes: str
    logo_path: str
    created_at: str
    contacts: list[SupplierContact] = []

    # v7.1.0 — KPIs / activity computed on demand, all optional + safe defaults
    # so existing callers that don't ask for stats keep working.
    engaged_total: float = 0          # all-time sum of doc amounts (accepted wins over declared)
    engaged_ytd: float = 0            # same but filtered to current calendar year
    active_dossiers_count: int = 0    # dossiers where status != 'archive'
    total_dossiers_count: int = 0
    last_interaction: str | None = None  # max(documents.doc_date) — ISO date
    status_auto: str = "jamais_utilise"  # 'actif_recent' | 'actif' | 'dormant' | 'inactif' | 'jamais_utilise'
    domain_color: str = ""              # hex color from supplier_domains, if matched
    timeline: list[TimelineEvent] = []  # populated only by GET /{id} (detail endpoint)
    services: list[ServiceCount] = []   # populated only by GET /{id} (detail endpoint)

    model_config = ConfigDict(from_attributes=True)


class DomainCreate(BaseModel):
    name: str
    color_hex: str = "#64748B"
    icon_key: str = "briefcase"
    sort_order: int = 0


class DomainUpdate(DomainCreate):
    pass


class DomainResponse(BaseModel):
    id: int
    name: str
    color_hex: str
    icon_key: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
