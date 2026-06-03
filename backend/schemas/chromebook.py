from __future__ import annotations

from pydantic import BaseModel, ConfigDict


# ── Teachers ──────────────────────────────────────────────────────────────

class TeacherResponse(BaseModel):
    id: int
    google_user_id: str = ""
    email: str
    full_name: str = ""
    given_name: str = ""
    family_name: str = ""
    google_ou_path: str = ""
    is_suspended: bool = False
    status_local: str = "present"  # present / partant / arrivant / parti
    arrival_date: str | None = None
    departure_date: str | None = None
    notes: str = ""
    last_sync: str = ""
    created_at: str = ""
    updated_at: str = ""

    # KPIs/enrichments (computed by the list endpoint)
    chromebook_count: int = 0
    primary_chromebook_id: int | None = None
    primary_chromebook_serial: str = ""
    primary_chromebook_model: str = ""

    model_config = ConfigDict(from_attributes=True)


class TeacherUpdate(BaseModel):
    """Local-only fields editable by the user. Google-side fields are read-only."""
    status_local: str | None = None
    arrival_date: str | None = None
    departure_date: str | None = None
    notes: str | None = None


# ── Chromebooks ───────────────────────────────────────────────────────────

class ChromebookResponse(BaseModel):
    id: int
    google_device_id: str
    serial_number: str = ""
    model: str = ""
    annotated_asset_id: str = ""
    annotated_user: str = ""
    org_unit_path: str = ""
    google_status: str = ""  # ACTIVE / DEPROVISIONED / DISABLED / ...
    last_enrollment_time: str | None = None
    support_end_date: str | None = None
    last_user_email: str = ""
    assigned_teacher_id: int | None = None
    binding_source: str = "none"  # annotated / recent_user / manual / none
    status_local: str = "en_service"
    service_start_date: str | None = None
    return_date: str | None = None
    notes_local: str = ""
    last_sync: str = ""
    created_at: str = ""
    updated_at: str = ""

    # Joined display fields
    teacher_email: str = ""
    teacher_full_name: str = ""
    teacher_status_local: str = ""

    model_config = ConfigDict(from_attributes=True)


class ChromebookUpdate(BaseModel):
    """Local-only edits (status workflow, notes, dates, manual rebind)."""
    status_local: str | None = None
    service_start_date: str | None = None
    return_date: str | None = None
    notes_local: str | None = None
    # Manual override of the auto-binding. Set to a teacher id, or to null
    # to explicitly clear the assignment (which also flips binding_source to
    # 'manual' so the next sync doesn't silently rebind it).
    assigned_teacher_id: int | None = None
    clear_assignment: bool = False  # explicit "unbind" intent


# ── Assignment history ────────────────────────────────────────────────────

class AssignmentHistoryEntry(BaseModel):
    id: int
    chromebook_id: int
    teacher_id: int | None = None
    teacher_email: str = ""
    teacher_name: str = ""
    assigned_at: str
    returned_at: str | None = None
    condition_in: str = ""
    condition_out: str = ""
    notes: str = ""

    model_config = ConfigDict(from_attributes=True)


# ── Sync result ───────────────────────────────────────────────────────────

class SyncStats(BaseModel):
    devices_total: int = 0
    devices_inserted: int = 0
    devices_updated: int = 0
    devices_rebound: int = 0   # changed assigned_teacher_id during this sync
    devices_orphaned: int = 0  # ended up with binding_source=none
    teachers_total: int = 0
    teachers_inserted: int = 0
    teachers_updated: int = 0
    duration_seconds: float = 0.0
    started_at: str = ""
    finished_at: str = ""
    errors: list[str] = []
