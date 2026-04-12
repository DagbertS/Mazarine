from __future__ import annotations
import hashlib
import os
import uuid
import json
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from app.database import get_conn, _row_dict

SESSION_DURATION_HOURS = 72

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()

def _generate_salt() -> str:
    return os.urandom(32).hex()

def _generate_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex

async def create_user(email: str, username: str, password: str, role: str = "user") -> dict:
    salt = _generate_salt()
    pw_hash = _hash_password(password, salt)
    uid = f"usr-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    conf_token = uuid.uuid4().hex
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO users (id, email, username, password_hash, salt, display_name, role, status,
               email_confirmed, confirmation_token, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, email.lower(), username, pw_hash, salt, username, role, "pending", 0, conf_token, now, now),
        )
        await conn.commit()
        await _log_activity(conn, uid, "register", {"email": email})
        return {"id": uid, "email": email, "username": username, "confirmation_token": conf_token}
    finally:
        await conn.close()

async def confirm_email(token: str) -> bool:
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT id FROM users WHERE confirmation_token = ?", (token,))
        row = await cur.fetchone()
        if not row:
            return False
        await conn.execute(
            "UPDATE users SET email_confirmed = 1, status = 'active', confirmation_token = NULL, updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), row["id"]),
        )
        await conn.commit()
        return True
    finally:
        await conn.close()

async def login(email_or_username: str, password: str) -> dict | None:
    conn = await get_conn()
    try:
        cur = await conn.execute(
            "SELECT * FROM users WHERE (email = ? OR username = ?) AND status != 'blocked'",
            (email_or_username.lower(), email_or_username),
        )
        user = await cur.fetchone()
        if not user:
            return None
        user = _row_dict(user)
        pw_hash = _hash_password(password, user["salt"])
        if pw_hash != user["password_hash"]:
            return None
        token = _generate_token()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        sid = f"ses-{uuid.uuid4().hex[:12]}"
        await conn.execute(
            "INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at) VALUES (?,?,?,?,?)",
            (sid, user["id"], token_hash, now.isoformat(), (now + timedelta(hours=SESSION_DURATION_HOURS)).isoformat()),
        )
        await conn.execute(
            "UPDATE users SET login_count = login_count + 1, last_login = ?, updated_at = ? WHERE id = ?",
            (now.isoformat(), now.isoformat(), user["id"]),
        )
        await conn.commit()
        await _log_activity(conn, user["id"], "login", {})
        user.pop("password_hash", None)
        user.pop("salt", None)
        user.pop("confirmation_token", None)
        return {"user": user, "token": token, "session_id": sid}
    finally:
        await conn.close()

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = await get_conn()
    try:
        cur = await conn.execute(
            """SELECT u.* FROM users u JOIN sessions s ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.revoked = 0 AND s.expires_at > ? AND u.status != 'blocked'""",
            (token_hash, datetime.now(timezone.utc).isoformat()),
        )
        user = await cur.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        user = _row_dict(user)
        user.pop("password_hash", None)
        user.pop("salt", None)
        user.pop("confirmation_token", None)
        return user
    finally:
        await conn.close()

async def require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def logout(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = await get_conn()
        try:
            await conn.execute("UPDATE sessions SET revoked = 1 WHERE token_hash = ?", (token_hash,))
            await conn.commit()
        finally:
            await conn.close()

async def _log_activity(conn, user_id: str, action: str, details: dict):
    aid = f"act-{uuid.uuid4().hex[:12]}"
    await conn.execute(
        "INSERT INTO activity_log (id, user_id, action, details, timestamp) VALUES (?,?,?,?,?)",
        (aid, user_id, action, json.dumps(details), datetime.now(timezone.utc).isoformat()),
    )
    await conn.commit()

async def log_activity(user_id: str, action: str, details: dict):
    conn = await get_conn()
    try:
        await _log_activity(conn, user_id, action, details)
    finally:
        await conn.close()
