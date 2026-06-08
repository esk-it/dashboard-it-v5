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
    # v7.2.1 diagnostic — surface why bindings fail.
    devices_with_annotated: int = 0     # Google returned a non-empty annotatedUser
    devices_with_recent_user: int = 0   # Google returned a recentUsers[0].email
    devices_with_asset_id_email: int = 0  # v7.2.6 — annotatedAssetId looked like an email
    matched_via_asset_id: int = 0       # v7.2.6 — highest-priority binding source
    matched_via_annotated: int = 0
    matched_via_recent_user: int = 0
    # Up to 5 sample (device_serial, annotated_user, last_user_email) tuples for
    # the orphan cohort so the UI can show "voici ce que Google nous a renvoyé".
    orphan_samples: list[dict] = []
    # v7.2.4 — annotated_user emails that we DIDN'T use for binding because
    # they showed up on too many devices (likely a shared admin/service
    # account, not a real assignee). Each entry: {email, device_count}.
    shared_annotated_skipped: list[dict] = []
    duration_seconds: float = 0.0
    started_at: str = ""
    finished_at: str = ""
    errors: list[str] = []
