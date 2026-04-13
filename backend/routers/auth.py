"""Authentication & user management endpoints."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from ..database import get_raw_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT-like token using HMAC-SHA256 (no external dependency)
_SECRET = secrets.token_hex(32)  # Generated once per app lifetime


# ── Models ──

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str = ""
    password: str
    display_name: str = ""


class UserUpdate(BaseModel):
    email: str | None = None
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None
    avatar_color: str | None = None


# ── Helpers ──

def _hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored hash."""
    parts = password_hash.split(":", 1)
    if len(parts) != 2:
        return False
    salt, stored_hash = parts
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return hmac.compare_digest(h, stored_hash)


def _create_token(user_id: int, username: str, role: str, ttl: int = 86400 * 30) -> str:
    """Create a simple JWT-like token (header.payload.signature)."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}))
    payload_data = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": int(time.time()) + ttl,
        "iat": int(time.time()),
    }
    payload = _b64url(json.dumps(payload_data))
    signature = hmac.new(_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"{header}.{payload}.{signature}"


def _b64url(data: str) -> str:
    import base64
    return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()


def _user_dict(row) -> dict:
    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "display_name": row[3],
        "role": row[5],
        "avatar_color": row[6],
        "is_active": bool(row[7]),
        "created_at": row[8],
        "last_login": row[9],
    }


# ── Seed default admin ──

async def ensure_default_admin(db):
    """Create default admin user if no users exist."""
    rows = await db.execute_fetchall("SELECT COUNT(*) FROM users")
    if rows[0][0] == 0:
        now = datetime.now(timezone.utc).isoformat()
        pw_hash = _hash_password("admin123")
        await db.execute(
            """INSERT INTO users (username, email, display_name, password_hash, role, avatar_color, is_active, created_at, last_login)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("admin", "admin@local", "Administrateur", pw_hash, "admin", "#8869e1", 1, now, ""),
        )
        await db.commit()
        logger.info("Default admin user created (admin / admin123)")


# ── Auth endpoints ──

@router.post("/login")
async def login(body: LoginRequest, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, username, email, display_name, password_hash, role, avatar_color, is_active, created_at, last_login FROM users WHERE username=?",
        (body.username,),
    )
    if not rows:
        raise HTTPException(401, "Nom d'utilisateur ou mot de passe incorrect")

    user_row = rows[0]
    if not _verify_password(body.password, user_row[4]):
        raise HTTPException(401, "Nom d'utilisateur ou mot de passe incorrect")

    if not user_row[7]:  # is_active
        raise HTTPException(403, "Ce compte est desactive")

    # Update last_login
    now = datetime.now(timezone.utc).isoformat()
    await db.execute("UPDATE users SET last_login=? WHERE id=?", (now, user_row[0]))
    await db.commit()

    user = _user_dict(user_row)
    access_token = _create_token(user["id"], user["username"], user["role"], ttl=86400 * 30)
    refresh_token = _create_token(user["id"], user["username"], user["role"], ttl=86400 * 90)

    # Detect default password — force change on first login
    must_change = body.password == "admin123"

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "must_change_password": must_change,
        "user": user,
    }


@router.post("/register")
async def register(body: RegisterRequest, db=Depends(get_raw_db)):
    # Check if username exists
    existing = await db.execute_fetchall("SELECT id FROM users WHERE username=?", (body.username,))
    if existing:
        raise HTTPException(400, "Ce nom d'utilisateur est deja pris")

    now = datetime.now(timezone.utc).isoformat()
    pw_hash = _hash_password(body.password)

    # First user gets admin role, others get user role
    count = await db.execute_fetchall("SELECT COUNT(*) FROM users")
    role = "admin" if count[0][0] == 0 else "user"

    colors = ['#8869e1', '#F59E0B', '#3A9B94', '#EC4899', '#3B82F6', '#EF4444', '#22C55E']
    color = colors[hash(body.username) % len(colors)]

    cursor = await db.execute(
        """INSERT INTO users (username, email, display_name, password_hash, role, avatar_color, is_active, created_at, last_login)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (body.username, body.email, body.display_name or body.username, pw_hash, role, color, 1, now, ""),
    )
    await db.commit()
    user_id = cursor.lastrowid

    user = {
        "id": user_id, "username": body.username, "email": body.email,
        "display_name": body.display_name or body.username, "role": role,
        "avatar_color": color, "is_active": True, "created_at": now, "last_login": "",
    }

    access_token = _create_token(user_id, body.username, role, ttl=86400 * 30)
    refresh_token = _create_token(user_id, body.username, role, ttl=86400 * 90)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }


@router.post("/refresh")
async def refresh(body: dict = Body(...), db=Depends(get_raw_db)):
    rt = body.get("refresh_token", "")
    if not rt:
        raise HTTPException(401, "No refresh token")
    try:
        import base64
        parts = rt.split(".")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        if payload["exp"] < time.time():
            raise HTTPException(401, "Refresh token expired")

        user_id = payload["sub"]
        rows = await db.execute_fetchall(
            "SELECT id, username, email, display_name, password_hash, role, avatar_color, is_active, created_at, last_login FROM users WHERE id=?",
            (user_id,),
        )
        if not rows or not rows[0][7]:
            raise HTTPException(401, "User not found or disabled")

        user = _user_dict(rows[0])
        access_token = _create_token(user["id"], user["username"], user["role"], ttl=86400 * 30)
        new_refresh = _create_token(user["id"], user["username"], user["role"], ttl=86400 * 90)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "user": user,
        }
    except (KeyError, json.JSONDecodeError, IndexError):
        raise HTTPException(401, "Invalid refresh token")


# ── User management endpoints (admin only for now) ──

@router.get("/users")
async def list_users(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT id, username, email, display_name, password_hash, role, avatar_color, is_active, created_at, last_login FROM users ORDER BY id"
    )
    return {"users": [_user_dict(r) for r in rows]}


@router.post("/users")
async def create_user(body: RegisterRequest, db=Depends(get_raw_db)):
    existing = await db.execute_fetchall("SELECT id FROM users WHERE username=?", (body.username,))
    if existing:
        raise HTTPException(400, "Ce nom d'utilisateur est deja pris")

    now = datetime.now(timezone.utc).isoformat()
    pw_hash = _hash_password(body.password)
    colors = ['#8869e1', '#F59E0B', '#3A9B94', '#EC4899', '#3B82F6', '#EF4444', '#22C55E']
    color = colors[hash(body.username) % len(colors)]

    cursor = await db.execute(
        """INSERT INTO users (username, email, display_name, password_hash, role, avatar_color, is_active, created_at, last_login)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (body.username, body.email, body.display_name or body.username, pw_hash, "user", color, 1, now, ""),
    )
    await db.commit()
    return {"ok": True, "id": cursor.lastrowid}


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, db=Depends(get_raw_db)):
    rows = await db.execute_fetchall("SELECT id FROM users WHERE id=?", (user_id,))
    if not rows:
        raise HTTPException(404, "User not found")

    updates = []
    params = []
    if body.email is not None:
        updates.append("email=?"); params.append(body.email)
    if body.display_name is not None:
        updates.append("display_name=?"); params.append(body.display_name)
    if body.password is not None:
        updates.append("password_hash=?"); params.append(_hash_password(body.password))
    if body.role is not None:
        updates.append("role=?"); params.append(body.role)
    if body.is_active is not None:
        updates.append("is_active=?"); params.append(1 if body.is_active else 0)
    if body.avatar_color is not None:
        updates.append("avatar_color=?"); params.append(body.avatar_color)

    if updates:
        params.append(user_id)
        await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", tuple(params))
        await db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db=Depends(get_raw_db)):
    # Prevent deleting last admin
    admins = await db.execute_fetchall("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1")
    user = await db.execute_fetchall("SELECT role FROM users WHERE id=?", (user_id,))
    if user and user[0][0] == "admin" and admins[0][0] <= 1:
        raise HTTPException(400, "Impossible de supprimer le dernier administrateur")

    await db.execute("DELETE FROM users WHERE id=?", (user_id,))
    await db.commit()
    return {"ok": True}


class ChangePasswordRequest(BaseModel):
    user_id: int
    new_password: str


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, db=Depends(get_raw_db)):
    if not body.new_password or len(body.new_password) < 4:
        raise HTTPException(400, "Le mot de passe doit contenir au moins 4 caracteres")
    if body.new_password == "admin123":
        raise HTTPException(400, "Choisissez un mot de passe different du mot de passe par defaut")
    pw_hash = _hash_password(body.new_password)
    await db.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, body.user_id))
    await db.commit()
    return {"ok": True}
