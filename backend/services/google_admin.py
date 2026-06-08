"""Google Admin SDK Directory API client.

Reuses the OAuth token managed by `google_calendar` (single Google connection
shared across modules). Only consumes 2 scopes:

  - admin.directory.device.chromeos.readonly
  - admin.directory.user.readonly

Both endpoints used here support OU-path filtering at the source so we only
pull what we care about (the teacher OU, not the whole domain's 500+ devices).
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import httpx

from . import google_calendar

logger = logging.getLogger(__name__)


_API_BASE = "https://admin.googleapis.com/admin/directory/v1"

# Default page sizes — Google API max is 200 for devices, 500 for users.
_DEVICE_PAGE_SIZE = 200
_USER_PAGE_SIZE = 500


def _has_admin_scope() -> bool:
    """True if the persisted Google config carries the Directory scopes."""
    cfg = google_calendar.load_config()
    return bool(cfg and cfg.get("refresh_token"))


async def fetch_chromeos_devices(
    org_unit_path: str,
    *,
    include_descendants: bool = False,
) -> list[dict[str, Any]]:
    """Pull every ChromeOS device under the given OU.

    `include_descendants` toggles whether we also pull devices in child OUs.
    Default False so the user gets exactly the OU they configured. The
    Directory API parameter `includeChildOrgunits` does that.
    """
    token = await google_calendar._ensure_valid_token()
    out: list[dict[str, Any]] = []
    page_token: str | None = None

    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            params: dict[str, Any] = {
                "orgUnitPath": org_unit_path,
                "maxResults": _DEVICE_PAGE_SIZE,
                "projection": "FULL",
            }
            if include_descendants:
                params["includeChildOrgunits"] = "true"
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{_API_BASE}/customer/my_customer/devices/chromeos",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if resp.status_code == 403:
                # Most likely cause: scope missing or user is not Super Admin.
                raise PermissionError(
                    "Accès refusé par Google. Vérifie que tu es Super Admin "
                    "Workspace et que tu as re-validé les permissions du programme "
                    "(les scopes Admin Directory ont été ajoutés en v7.2.0)."
                )
            resp.raise_for_status()
            data = resp.json()
            out.extend(data.get("chromeosdevices", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return out


async def fetch_users(
    org_unit_path: str,
    *,
    include_descendants: bool = True,
) -> list[dict[str, Any]]:
    """Pull users under the given OU path.

    Implementation note (v7.2.2): Google's `users.list` `query=orgUnitPath='...'`
    syntax chokes on paths with spaces, dots or accented characters (returns
    HTTP 400 Bad Request) — even when escaped per the docs. We work around
    by pulling every user in the customer (paginated) and filtering by
    `orgUnitPath` client-side. For schools with ~500-3000 Workspace accounts
    this adds ~1-2s on top of the device sync; well worth the reliability.

    `include_descendants` (default True): also returns users in sub-OUs of
    the target path. Useful if profs are nested by establishment
    (e.g. `/Profs/NDK`, `/Profs/SU`). Set False to require exact OU.
    """
    token = await google_calendar._ensure_valid_token()
    out: list[dict[str, Any]] = []
    page_token: str | None = None

    target = (org_unit_path or "").rstrip("/")
    if not target:
        return []

    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            params: dict[str, Any] = {
                "customer": "my_customer",
                "maxResults": _USER_PAGE_SIZE,
                "projection": "full",
            }
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{_API_BASE}/users",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if resp.status_code == 403:
                raise PermissionError(
                    "Accès refusé par Google sur la lecture des utilisateurs. "
                    "Vérifie le scope admin.directory.user.readonly."
                )
            resp.raise_for_status()
            data = resp.json()

            for u in data.get("users", []):
                ou = (u.get("orgUnitPath") or "").rstrip("/")
                if include_descendants:
                    # Match the target OR any path starting with target + "/".
                    if ou == target or ou.startswith(target + "/"):
                        out.append(u)
                else:
                    if ou == target:
                        out.append(u)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return out


# ── Extraction helpers ────────────────────────────────────────────────────
#
# Google's payloads are deeply nested; small helpers below normalise them to
# flat dicts that the routers can store in SQLite directly.


def normalize_chromeos_device(raw: dict[str, Any]) -> dict[str, Any]:
    """Pick the fields we persist locally from a ChromeOS device JSON."""
    recent_users = raw.get("recentUsers") or []
    # recentUsers is sorted by date DESC; index 0 is the most recent.
    last_user_email = ""
    for u in recent_users:
        e = (u.get("email") or "").strip()
        if e:
            last_user_email = e
            break

    return {
        "google_device_id": raw.get("deviceId", ""),
        "serial_number": raw.get("serialNumber", "") or "",
        "model": raw.get("model", "") or "",
        "annotated_asset_id": raw.get("annotatedAssetId", "") or "",
        "annotated_user": (raw.get("annotatedUser", "") or "").strip(),
        "org_unit_path": raw.get("orgUnitPath", "") or "",
        "google_status": raw.get("status", "") or "",
        "last_enrollment_time": raw.get("lastEnrollmentTime") or None,
        "support_end_date": raw.get("supportEndDate") or None,
        "last_user_email": last_user_email,
    }


def normalize_user(raw: dict[str, Any]) -> dict[str, Any]:
    """Pick the fields we persist locally from a Workspace user JSON."""
    name = raw.get("name") or {}
    return {
        "google_user_id": raw.get("id", "") or "",
        "email": (raw.get("primaryEmail", "") or "").strip().lower(),
        "full_name": (name.get("fullName", "") or "").strip(),
        "given_name": (name.get("givenName", "") or "").strip(),
        "family_name": (name.get("familyName", "") or "").strip(),
        "google_ou_path": raw.get("orgUnitPath", "") or "",
        "is_suspended": 1 if raw.get("suspended") else 0,
    }
