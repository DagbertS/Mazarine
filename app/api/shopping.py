import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user
from app.database import get_conn, _row_dict
from app.services.consolidator import consolidate_ingredients, assign_aisle

router = APIRouter(prefix="/api/shopping", tags=["shopping"])

class ListCreate(BaseModel):
    name: str

class ItemCreate(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    aisle: Optional[str] = None
    recipe_id: Optional[str] = None

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    aisle: Optional[str] = None
    checked: Optional[bool] = None

@router.get("/lists")
async def get_lists(request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute(
            """SELECT sl.*, COUNT(si.id) as item_count,
               SUM(CASE WHEN si.checked = 1 THEN 1 ELSE 0 END) as checked_count
               FROM shopping_lists sl LEFT JOIN shopping_items si ON sl.id = si.list_id
               WHERE sl.user_id = ? GROUP BY sl.id ORDER BY sl.updated_at DESC""",
            (user["id"],))
        lists = [_row_dict(l) for l in await cur.fetchall()]
        return {"lists": lists}
    finally:
        await conn.close()

@router.post("/lists")
async def create_list(body: ListCreate, request: Request):
    user = await get_current_user(request)
    lid = f"shl-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    conn = await get_conn()
    try:
        await conn.execute("INSERT INTO shopping_lists (id, user_id, name, created_at, updated_at) VALUES (?,?,?,?,?)",
                           (lid, user["id"], body.name, now, now))
        await conn.commit()
        return {"id": lid, "status": "created"}
    finally:
        await conn.close()

@router.delete("/lists/{list_id}")
async def delete_list(list_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM shopping_items WHERE list_id = ?", (list_id,))
        await conn.execute("DELETE FROM shopping_lists WHERE id = ? AND user_id = ?", (list_id, user["id"]))
        await conn.commit()
        return {"status": "deleted"}
    finally:
        await conn.close()

@router.get("/lists/{list_id}/items")
async def get_items(list_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute(
            """SELECT si.*, r.title as recipe_title FROM shopping_items si
               LEFT JOIN recipes r ON si.recipe_id = r.id
               WHERE si.list_id = ? ORDER BY si.aisle, si.name""",
            (list_id,))
        items = [_row_dict(i) for i in await cur.fetchall()]
        grouped = {}
        for item in items:
            aisle = item.get("aisle") or "Other"
            grouped.setdefault(aisle, []).append(item)
        return {"items": items, "grouped": grouped}
    finally:
        await conn.close()

@router.post("/lists/{list_id}/items")
async def add_item(list_id: str, body: ItemCreate, request: Request):
    user = await get_current_user(request)
    iid = f"shi-{uuid.uuid4().hex[:12]}"
    aisle = body.aisle or assign_aisle(body.name)
    conn = await get_conn()
    try:
        await conn.execute(
            "INSERT INTO shopping_items (id, list_id, name, quantity, unit, aisle, recipe_id) VALUES (?,?,?,?,?,?,?)",
            (iid, list_id, body.name, body.quantity, body.unit, aisle, body.recipe_id))
        await conn.execute("UPDATE shopping_lists SET updated_at = ? WHERE id = ?",
                           (datetime.now(timezone.utc).isoformat(), list_id))
        await conn.commit()
        return {"id": iid, "status": "added"}
    finally:
        await conn.close()

@router.put("/items/{item_id}")
async def update_item(item_id: str, body: ItemUpdate, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        updates = body.model_dump(exclude_none=True)
        if "checked" in updates:
            updates["checked"] = 1 if updates["checked"] else 0
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [item_id]
            await conn.execute(f"UPDATE shopping_items SET {set_clause} WHERE id = ?", vals)
            await conn.commit()
        return {"status": "updated"}
    finally:
        await conn.close()

@router.delete("/items/{item_id}")
async def delete_item(item_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
        await conn.commit()
        return {"status": "deleted"}
    finally:
        await conn.close()

@router.post("/lists/{list_id}/add-recipe/{recipe_id}")
async def add_recipe_to_list(list_id: str, recipe_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT ingredients FROM recipes WHERE id = ? AND user_id = ?",
                                 (recipe_id, user["id"]))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recipe not found")
        ingredients = json.loads(row["ingredients"] or "[]")
        cur_existing = await conn.execute("SELECT name, quantity, unit, id FROM shopping_items WHERE list_id = ?", (list_id,))
        existing = [_row_dict(e) for e in await cur_existing.fetchall()]
        merged = consolidate_ingredients(ingredients, existing)

        for item in merged:
            if item.get("_existing_id"):
                await conn.execute("UPDATE shopping_items SET quantity = ?, unit = ? WHERE id = ?",
                                   (item["quantity"], item["unit"], item["_existing_id"]))
            else:
                iid = f"shi-{uuid.uuid4().hex[:12]}"
                aisle = assign_aisle(item["name"])
                await conn.execute(
                    "INSERT INTO shopping_items (id, list_id, name, quantity, unit, aisle, recipe_id) VALUES (?,?,?,?,?,?,?)",
                    (iid, list_id, item["name"], item.get("quantity"), item.get("unit"), aisle, recipe_id))

        await conn.execute("UPDATE shopping_lists SET updated_at = ? WHERE id = ?",
                           (datetime.now(timezone.utc).isoformat(), list_id))
        await conn.commit()
        return {"status": "added", "items_added": len(merged)}
    finally:
        await conn.close()
