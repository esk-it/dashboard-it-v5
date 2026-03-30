"""Authentication router – JWT-based login/register/refresh."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..database import get_raw_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Secret key – in production, use an env variable
SECRET_KEY = os.environ.get("ITMANAGER_JWT_SECRET", "itmanager-dev-secret-key-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30


# --------------- Schemas ---------------

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None
    current_password: str | None = None
    new_password: str | None = None


# --------------- Helpers ---------------

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _user_dict(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "display_name": row["display_name"] or row["username"],
        "role": row["role"],
    }


# --------------- Routes ---------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_raw_db)):
    cursor = await db.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (body.username,),
    )
    user = await cursor.fetchone()
    if not user or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    await db.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), user["id"]),
    )
    await db.commit()

    access_token = _create_token(
        {"sub": str(user["id"]), "username": user["username"], "role": user["role"]},
        timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    )
    refresh_token = _create_token(
        {"sub": str(user["id"]), "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_dict(user),
    )


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db=Depends(get_raw_db)):
    # Check uniqueness
    cursor = await db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (body.username, body.email),
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    password_hash = _hash_password(body.password)
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO users (username, email, password_hash, display_name, role, is_active, created_at)
           VALUES (?, ?, ?, ?, 'user', 1, ?)""",
        (body.username, body.email, password_hash, body.display_name or body.username, now),
    )
    await db.commit()

    cursor = await db.execute("SELECT * FROM users WHERE username = ?", (body.username,))
    user = await cursor.fetchone()

    access_token = _create_token(
        {"sub": str(user["id"]), "username": user["username"], "role": user["role"]},
        timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    )
    refresh_token = _create_token(
        {"sub": str(user["id"]), "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_dict(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db=Depends(get_raw_db)):
    payload = _decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload["sub"]
    cursor = await db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))
    user = await cursor.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = _create_token(
        {"sub": str(user["id"]), "username": user["username"], "role": user["role"]},
        timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    )
    new_refresh = _create_token(
        {"sub": str(user["id"]), "type": "refresh"},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=_user_dict(user),
    )


@router.get("/me")
async def get_me(db=Depends(get_raw_db)):
    """Requires Authorization header. Called from frontend auth guard."""
    # This is a lightweight check – the middleware handles token validation.
    # We just need to return user info.
    from fastapi import Request
    # This endpoint is protected by the global middleware in main.py
    # The user_id is set by middleware on request.state
    # For now, we'll decode manually from the header
    return {"message": "Use the middleware-injected user"}


@router.put("/me")
async def update_profile(body: UpdateProfileRequest, db=Depends(get_raw_db)):
    # Placeholder – will be called with token in header
    raise HTTPException(status_code=501, detail="Not implemented yet")
