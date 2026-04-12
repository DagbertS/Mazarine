import hashlib
import os
import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import require_admin
from app.database import get_conn, _row_dict

router = APIRouter(prefix="/api/admin", tags=["admin"])

class UserUpdateAdmin(BaseModel):
    status: Optional[str] = None
    role: Optional[str] = None
    can_upload: Optional[bool] = None
    can_download: Optional[bool] = None

@router.get("/users")
async def list_users(request: Request):
    await require_admin(request)
    conn = await get_conn()
    try:
        cur = await conn.execute(
            """SELECT id, email, username, display_name, role, status, email_confirmed,
               can_upload, can_download, login_count, last_login, last_search,
               upload_count, created_at, updated_at FROM users ORDER BY created_at DESC""")
        users = [_row_dict(u) for u in await cur.fetchall()]
        return {"users": users}
    finally:
        await conn.close()

@router.get("/users/{user_id}")
async def get_user(user_id: str, request: Request):
    await require_admin(request)
    conn = await get_conn()
    try:
        cur = await conn.execute(
            """SELECT id, email, username, display_name, role, status, email_confirmed,
               can_upload, can_download, login_count, last_login, last_search,
               upload_count, created_at, updated_at FROM users WHERE id = ?""", (user_id,))
        user = await cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user = _row_dict(user)
        cur_a = await conn.execute(
            "SELECT action, details, timestamp FROM activity_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT 50",
            (user_id,))
        user["activity"] = [_row_dict(a) for a in await cur_a.fetchall()]
        cur_r = await conn.execute("SELECT COUNT(*) FROM recipes WHERE user_id = ?", (user_id,))
        user["recipe_count"] = (await cur_r.fetchone())[0]
        return user
    finally:
        await conn.close()

@router.put("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdateAdmin, request: Request):
    await require_admin(request)
    conn = await get_conn()
    try:
        updates = {}
        if body.status is not None:
            updates["status"] = body.status
        if body.role is not None:
            updates["role"] = body.role
        if body.can_upload is not None:
            updates["can_upload"] = 1 if body.can_upload else 0
        if body.can_download is not None:
            updates["can_download"] = 1 if body.can_download else 0
        if not updates:
            return {"status": "no changes"}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [user_id]
        await conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", vals)
        await conn.commit()
        return {"status": "updated"}
    finally:
        await conn.close()

@router.post("/users/{user_id}/block")
async def block_user(user_id: str, request: Request):
    await require_admin(request)
    conn = await get_conn()
    try:
        await conn.execute("UPDATE users SET status = 'blocked', updated_at = ? WHERE id = ?",
                           (datetime.now(timezone.utc).isoformat(), user_id))
        await conn.execute("UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        await conn.commit()
        return {"status": "blocked"}
    finally:
        await conn.close()

@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: str, request: Request):
    await require_admin(request)
    conn = await get_conn()
    try:
        await conn.execute("UPDATE users SET status = 'active', updated_at = ? WHERE id = ?",
                           (datetime.now(timezone.utc).isoformat(), user_id))
        await conn.commit()
        return {"status": "unblocked"}
    finally:
        await conn.close()

@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, request: Request):
    await require_admin(request)
    new_password = uuid.uuid4().hex[:12]
    salt = os.urandom(32).hex()
    pw_hash = hashlib.pbkdf2_hmac("sha256", new_password.encode(), salt.encode(), 100_000).hex()
    conn = await get_conn()
    try:
        await conn.execute("UPDATE users SET password_hash = ?, salt = ?, updated_at = ? WHERE id = ?",
                           (pw_hash, salt, datetime.now(timezone.utc).isoformat(), user_id))
        await conn.execute("UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
        await conn.commit()
        return {"status": "password_reset", "new_password": new_password}
    finally:
        await conn.close()

@router.get("/stats")
async def admin_stats(request: Request):
    await require_admin(request)
    conn = await get_conn()
    try:
        total_users = (await (await conn.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active_users = (await (await conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")).fetchone())[0]
        total_recipes = (await (await conn.execute("SELECT COUNT(*) FROM recipes")).fetchone())[0]
        total_logins = (await (await conn.execute("SELECT COUNT(*) FROM activity_log WHERE action = 'login'")).fetchone())[0]

        cur = await conn.execute(
            """SELECT u.id, u.username, u.email, u.login_count, u.last_login, u.upload_count, u.last_search,
               COUNT(r.id) as recipe_count
               FROM users u LEFT JOIN recipes r ON u.id = r.user_id
               GROUP BY u.id ORDER BY u.login_count DESC LIMIT 20""")
        top_users = [_row_dict(u) for u in await cur.fetchall()]

        cur2 = await conn.execute(
            "SELECT action, COUNT(*) as count FROM activity_log GROUP BY action ORDER BY count DESC")
        action_stats = [_row_dict(a) for a in await cur2.fetchall()]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_recipes": total_recipes,
            "total_logins": total_logins,
            "top_users": top_users,
            "action_stats": action_stats,
        }
    finally:
        await conn.close()

@router.get("/activity")
async def admin_activity(request: Request, limit: int = 100, user_id: Optional[str] = None):
    await require_admin(request)
    conn = await get_conn()
    try:
        if user_id:
            cur = await conn.execute(
                """SELECT a.*, u.username FROM activity_log a LEFT JOIN users u ON a.user_id = u.id
                   WHERE a.user_id = ? ORDER BY a.timestamp DESC LIMIT ?""",
                (user_id, limit))
        else:
            cur = await conn.execute(
                """SELECT a.*, u.username FROM activity_log a LEFT JOIN users u ON a.user_id = u.id
                   ORDER BY a.timestamp DESC LIMIT ?""", (limit,))
        activities = [_row_dict(a) for a in await cur.fetchall()]
        return {"activities": activities}
    finally:
        await conn.close()
