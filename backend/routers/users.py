"""User management router – extends existing auth system."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from ..database import get_raw_db

router = APIRouter(prefix="/api/users", tags=["users"])

SECRET_KEY = os.environ.get("ITMANAGER_JWT_SECRET", "itmanager-dev-secret-key-change-me")
ALGORITHM = "HS256"

VALID_ROLES = ("admin", "user", "viewer")


# --------------- Schemas ---------------

class UserCreate(BaseModel):
    username: str
    email: str = ""
    password: str
    display_name: str = ""
    role: str = "user"


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    role: str
    avatar_url: str
    is_active: bool
    created_at: str
    last_login: str | None


class UserStatsResponse(BaseModel):
    total: int
    active: int
    inactive: int
    by_role: dict[str, int]


# --------------- Helpers ---------------

def _get_current_user(request: Request) -> dict:
    """Extract user info from the Authorization header JWT token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "id": int(payload["sub"]),
            "username": payload.get("username", ""),
            "role": payload.get("role", "user"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")


def _require_admin(current_user: dict):
    """Raise 403 if the current user is not an admin."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _row_to_user(row) -> dict:
    """Convert a DB row to a user dict."""
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"] or "",
        "display_name": row["display_name"] or row["username"],
        "role": row["role"] or "user",
        "avatar_url": row["avatar_url"] or "",
        "is_active": bool(row["is_active"]) if "is_active" in row.keys() else True,
        "created_at": row["created_at"] or "",
        "last_login": row["last_login"],
    }


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


# --------------- Routes ---------------

@router.get("/stats", response_model=UserStatsResponse)
async def user_stats(request: Request, db=Depends(get_raw_db)):
    """Get user statistics."""
    _get_current_user(request)

    total_row = await db.execute_fetchall("SELECT COUNT(*) FROM users")
    total = total_row[0][0] if total_row else 0

    active_row = await db.execute_fetchall("SELECT COUNT(*) FROM users WHERE is_active = 1")
    active = active_row[0][0] if active_row else 0

    inactive = total - active

    role_rows = await db.execute_fetchall(
        "SELECT role, COUNT(*) as cnt FROM users GROUP BY role"
    )
    by_role = {r["role"]: r["cnt"] for r in role_rows}

    return UserStatsResponse(total=total, active=active, inactive=inactive, by_role=by_role)


@router.get("", response_model=list[UserResponse])
async def list_users(
    request: Request,
    search: str = Query(""),
    role: str = Query(""),
    is_active: bool | None = Query(None),
    db=Depends(get_raw_db),
):
    """List all users."""
    _get_current_user(request)

    query = """SELECT id, username, email, display_name, role, avatar_url,
                      is_active, created_at, last_login
               FROM users WHERE 1=1"""
    params: list = []

    if search:
        query += " AND (username LIKE ? OR display_name LIKE ? OR email LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    if role:
        query += " AND role = ?"
        params.append(role)

    if is_active is not None:
        query += " AND is_active = ?"
        params.append(1 if is_active else 0)

    query += " ORDER BY username ASC"

    rows = await db.execute_fetchall(query, params)
    return [UserResponse(**_row_to_user(r)) for r in rows]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, request: Request, db=Depends(get_raw_db)):
    """Get user details."""
    _get_current_user(request)

    rows = await db.execute_fetchall(
        """SELECT id, username, email, display_name, role, avatar_url,
                  is_active, created_at, last_login
           FROM users WHERE id = ?""",
        (user_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(**_row_to_user(rows[0]))


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, request: Request, db=Depends(get_raw_db)):
    """Create a new user. Admin only."""
    current_user = _get_current_user(request)
    _require_admin(current_user)

    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")

    # Check uniqueness
    existing = await db.execute_fetchall(
        "SELECT id FROM users WHERE username = ?", (body.username,),
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    if body.email:
        existing_email = await db.execute_fetchall(
            "SELECT id FROM users WHERE email = ?", (body.email,),
        )
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already exists")

    password_hash = _hash_password(body.password)
    now = datetime.now(timezone.utc).isoformat()

    cursor = await db.execute(
        """INSERT INTO users (username, email, password_hash, display_name, role, avatar_url, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, '', 1, ?)""",
        (body.username, body.email, password_hash, body.display_name or body.username, body.role, now),
    )
    await db.commit()
    user_id = cursor.lastrowid

    return await get_user(user_id, request, db)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, body: UserUpdate, request: Request, db=Depends(get_raw_db)):
    """Update a user. Admin can update any user; regular users can only update themselves."""
    current_user = _get_current_user(request)

    # Non-admin users can only update their own profile (limited fields)
    if current_user["role"] != "admin" and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")

    # Non-admin users cannot change role or is_active
    if current_user["role"] != "admin":
        if body.role is not None or body.is_active is not None:
            raise HTTPException(status_code=403, detail="Only admins can change role or active status")

    rows = await db.execute_fetchall("SELECT id FROM users WHERE id = ?", (user_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")

    updates = []
    params: list = []

    if body.display_name is not None:
        updates.append("display_name = ?")
        params.append(body.display_name)

    if body.email is not None:
        updates.append("email = ?")
        params.append(body.email)

    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}")
        updates.append("role = ?")
        params.append(body.role)

    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if body.is_active else 0)

    if body.avatar_url is not None:
        updates.append("avatar_url = ?")
        params.append(body.avatar_url)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(user_id)
    await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    await db.commit()

    return await get_user(user_id, request, db)


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(user_id: int, request: Request, db=Depends(get_raw_db)):
    """Deactivate a user (soft delete). Admin only."""
    current_user = _get_current_user(request)
    _require_admin(current_user)

    if current_user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    rows = await db.execute_fetchall("SELECT id FROM users WHERE id = ?", (user_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    await db.commit()
