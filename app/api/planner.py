import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user
from app.database import get_conn, _row_dict

router = APIRouter(prefix="/api/planner", tags=["planner"])

class MealPlanEntry(BaseModel):
    date: str
    slot: str
    recipe_id: Optional[str] = None
    note: Optional[str] = None

class MealPlanMove(BaseModel):
    new_date: str
    new_slot: str

@router.get("")
async def get_plan(request: Request, start: Optional[str] = None, end: Optional[str] = None):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        if start and end:
            cur = await conn.execute(
                """SELECT mp.*, r.title as recipe_title, r.photo_urls, r.prep_time_minutes, r.cook_time_minutes
                   FROM meal_plan mp LEFT JOIN recipes r ON mp.recipe_id = r.id
                   WHERE mp.user_id = ? AND mp.date >= ? AND mp.date <= ? ORDER BY mp.date, mp.slot""",
                (user["id"], start, end))
        else:
            cur = await conn.execute(
                """SELECT mp.*, r.title as recipe_title, r.photo_urls, r.prep_time_minutes, r.cook_time_minutes
                   FROM meal_plan mp LEFT JOIN recipes r ON mp.recipe_id = r.id
                   WHERE mp.user_id = ? ORDER BY mp.date DESC, mp.slot LIMIT 100""",
                (user["id"],))
        entries = [_row_dict(e) for e in await cur.fetchall()]
        for e in entries:
            if e.get("photo_urls") and isinstance(e["photo_urls"], str):
                e["photo_urls"] = json.loads(e["photo_urls"])
        return {"entries": entries}
    finally:
        await conn.close()

@router.post("")
async def add_to_plan(body: MealPlanEntry, request: Request):
    user = await get_current_user(request)
    if not body.recipe_id and not body.note:
        raise HTTPException(status_code=400, detail="Provide recipe_id or note")
    mid = f"mpl-{uuid.uuid4().hex[:12]}"
    conn = await get_conn()
    try:
        await conn.execute(
            "INSERT INTO meal_plan (id, user_id, date, slot, recipe_id, note) VALUES (?,?,?,?,?,?)",
            (mid, user["id"], body.date, body.slot, body.recipe_id, body.note))
        await conn.commit()
        return {"id": mid, "status": "created"}
    finally:
        await conn.close()

@router.put("/{entry_id}")
async def update_plan_entry(entry_id: str, body: MealPlanEntry, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE meal_plan SET date = ?, slot = ?, recipe_id = ?, note = ? WHERE id = ? AND user_id = ?",
            (body.date, body.slot, body.recipe_id, body.note, entry_id, user["id"]))
        await conn.commit()
        return {"status": "updated"}
    finally:
        await conn.close()

@router.put("/{entry_id}/move")
async def move_plan_entry(entry_id: str, body: MealPlanMove, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE meal_plan SET date = ?, slot = ? WHERE id = ? AND user_id = ?",
            (body.new_date, body.new_slot, entry_id, user["id"]))
        await conn.commit()
        return {"status": "moved"}
    finally:
        await conn.close()

@router.delete("/{entry_id}")
async def delete_plan_entry(entry_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM meal_plan WHERE id = ? AND user_id = ?", (entry_id, user["id"]))
        await conn.commit()
        return {"status": "deleted"}
    finally:
        await conn.close()

@router.post("/duplicate-week")
async def duplicate_week(request: Request, source_start: str = "", target_start: str = ""):
    user = await get_current_user(request)
    if not source_start or not target_start:
        raise HTTPException(status_code=400, detail="Provide source_start and target_start dates")
    from datetime import timedelta
    src_date = datetime.strptime(source_start, "%Y-%m-%d")
    tgt_date = datetime.strptime(target_start, "%Y-%m-%d")
    delta = tgt_date - src_date
    src_end = (src_date + timedelta(days=6)).strftime("%Y-%m-%d")
    conn = await get_conn()
    try:
        cur = await conn.execute(
            "SELECT * FROM meal_plan WHERE user_id = ? AND date >= ? AND date <= ?",
            (user["id"], source_start, src_end))
        entries = [_row_dict(e) for e in await cur.fetchall()]
        for e in entries:
            new_date = (datetime.strptime(e["date"], "%Y-%m-%d") + delta).strftime("%Y-%m-%d")
            mid = f"mpl-{uuid.uuid4().hex[:12]}"
            await conn.execute(
                "INSERT INTO meal_plan (id, user_id, date, slot, recipe_id, note) VALUES (?,?,?,?,?,?)",
                (mid, user["id"], new_date, e["slot"], e["recipe_id"], e["note"]))
        await conn.commit()
        return {"status": "duplicated", "entries_copied": len(entries)}
    finally:
        await conn.close()
