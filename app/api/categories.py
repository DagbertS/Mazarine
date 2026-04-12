import uuid
import json
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user
from app.database import get_conn, _row_dict

router = APIRouter(prefix="/api", tags=["categories"])

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    sort_order: Optional[int] = 0

class TagCreate(BaseModel):
    name: str
    type: Optional[str] = "custom"

# --- Categories ---

@router.get("/categories")
async def list_categories(request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT * FROM categories WHERE user_id = ? ORDER BY sort_order, name",
                                 (user["id"],))
        cats = [_row_dict(c) for c in await cur.fetchall()]
        tree = _build_tree(cats)
        return {"categories": tree}
    finally:
        await conn.close()

def _build_tree(cats: list) -> list:
    by_id = {c["id"]: {**c, "children": []} for c in cats}
    roots = []
    for c in cats:
        node = by_id[c["id"]]
        if c["parent_id"] and c["parent_id"] in by_id:
            by_id[c["parent_id"]]["children"].append(node)
        else:
            roots.append(node)
    return roots

@router.post("/categories")
async def create_category(body: CategoryCreate, request: Request):
    user = await get_current_user(request)
    cid = f"cat-{uuid.uuid4().hex[:8]}"
    conn = await get_conn()
    try:
        await conn.execute("INSERT INTO categories (id, user_id, name, parent_id, sort_order) VALUES (?,?,?,?,?)",
                           (cid, user["id"], body.name, body.parent_id, body.sort_order or 0))
        await conn.commit()
        return {"id": cid, "status": "created"}
    finally:
        await conn.close()

@router.put("/categories/{cat_id}")
async def update_category(cat_id: str, body: CategoryCreate, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("UPDATE categories SET name = ?, parent_id = ?, sort_order = ? WHERE id = ? AND user_id = ?",
                           (body.name, body.parent_id, body.sort_order or 0, cat_id, user["id"]))
        await conn.commit()
        return {"status": "updated"}
    finally:
        await conn.close()

@router.delete("/categories/{cat_id}")
async def delete_category(cat_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("UPDATE categories SET parent_id = NULL WHERE parent_id = ? AND user_id = ?",
                           (cat_id, user["id"]))
        await conn.execute("DELETE FROM recipe_categories WHERE category_id = ?", (cat_id,))
        await conn.execute("DELETE FROM categories WHERE id = ? AND user_id = ?", (cat_id, user["id"]))
        await conn.commit()
        return {"status": "deleted"}
    finally:
        await conn.close()

# --- Tags ---

@router.get("/tags")
async def list_tags(request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT t.*, COUNT(rt.recipe_id) as recipe_count FROM tags t LEFT JOIN recipe_tags rt ON t.id = rt.tag_id WHERE t.user_id = ? GROUP BY t.id ORDER BY t.name",
                                 (user["id"],))
        tags = [_row_dict(t) for t in await cur.fetchall()]
        return {"tags": tags}
    finally:
        await conn.close()

@router.post("/tags")
async def create_tag(body: TagCreate, request: Request):
    user = await get_current_user(request)
    tid = f"tag-{uuid.uuid4().hex[:8]}"
    conn = await get_conn()
    try:
        await conn.execute("INSERT INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                           (tid, user["id"], body.name, body.type or "custom"))
        await conn.commit()
        return {"id": tid, "status": "created"}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="Tag already exists")
        raise
    finally:
        await conn.close()

@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM recipe_tags WHERE tag_id = ?", (tag_id,))
        await conn.execute("DELETE FROM tags WHERE id = ? AND user_id = ?", (tag_id, user["id"]))
        await conn.commit()
        return {"status": "deleted"}
    finally:
        await conn.close()
