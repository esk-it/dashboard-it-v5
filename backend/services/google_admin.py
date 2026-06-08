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

    # Normalise: "/foo/" → "/foo", "/" → "" (= "match everything" mode).
    target = (org_unit_path or "").rstrip("/")
    match_all = (target == "")

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
                if match_all:
                    # User OU path '/' = root = pull everyone (escape hatch
                    # when the exact prof OU is unknown — the binding logic
                    # will still find the right matches via email).
                    out.append(u)
                    continue
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


async def get_user(email: str) -> dict[str, Any] | None:
    """Look up a single Workspace user by primary email (or alias).

    Returns the user JSON if found, None if Google returns 404 (no such user).
    Used by the Chromebook sync's "auto-discovery" pass (v7.2.9): when we
    see an email on a device that isn't in our synced teachers OU, we ask
    Google directly to confirm it's a Workspace account and pull it in.
    """
    if not email or "@" not in email:
        return None
    token = await google_calendar._ensure_valid_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_API_BASE}/users/{email}",
            headers={"Authorization": f"Bearer {token}"},
            params={"projection": "full"},
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 403:
            raise PermissionError(
                "Accès refusé par Google sur la lecture des utilisateurs. "
                "Vérifie le scope admin.directory.user.readonly."
            )
        # Some not-found responses come back as 400 too (especially for
        # alias-with-dots edge cases). Treat as "not found" so the sync
        # carries on instead of failing.
        if resp.status_code in (400, 410):
            return None
        resp.raise_for_status()
        return resp.json()


async def fetch_all_user_ou_paths() -> list[dict[str, Any]]:
    """Discovery helper: list every distinct orgUnitPath found across users,
    with a count and 3 sample emails per path. Lets the UI guide the user
    to the right path when they don't know the exact syntax.
    """
    all_users = await fetch_users("/", include_descendants=True)
    by_path: dict[str, dict[str, Any]] = {}
    for u in all_users:
        path = u.get("orgUnitPath") or "/"
        if path not in by_path:
            by_path[path] = {"path": path, "user_count": 0, "samples": []}
        by_path[path]["user_count"] += 1
        if len(by_path[path]["samples"]) < 3:
            email = (u.get("primaryEmail") or "").lower()
            if email:
                by_path[path]["samples"].append(email)
    # Most-populated first, then alphabetical to keep stable ordering.
    return sorted(
        by_path.values(),
        key=lambda x: (-x["user_count"], x["path"]),
    )


# ── Extraction helpers ────────────────────────────────────────────────────
#
# Google's payloads are deeply nested; small helpers below normalise them to
# flat dicts that the routers can store in SQLite directly.


def normalize_chromeos_device(raw: dict[str, Any]) -> dict[str, Any]:
    """Pick the fields we persist locally from a ChromeOS device JSON.

    v7.2.5 — collect the FULL recentUsers email list (not just [0]).
    Reality: index 0 may be a generic admin, a test account, or a masked
    `*****@*****.com`. By iterating later entries we still find the real
    teacher who's been using the device — which is the whole point of the
    auto-binding.
    """
    recent_users = raw.get("recentUsers") or []
    # recentUsers is sorted by Google by recency (most recent first).
    # We keep all non-empty + non-masked emails, preserving order.
    recent_user_emails: list[str] = []
    for u in recent_users:
        e = (u.get("email") or "").strip()
        if not e:
            continue
        # Skip Google's redaction marker (when device policy hides the email).
        if e.lower() == "*****@*****.com":
            continue
        recent_user_emails.append(e)

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
        # `last_user_email` keeps the most recent (index 0) for display.
        "last_user_email": recent_user_emails[0] if recent_user_emails else "",
        # `recent_user_emails` carries the full list for binding fallback.
        "recent_user_emails": recent_user_emails,
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
