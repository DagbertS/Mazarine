import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user, log_activity
from app.database import get_conn, _row_dict
from app.config import get_upload_dir
from pathlib import Path

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

class RecipeCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    ingredients: Optional[list] = []
    directions: Optional[list] = []
    servings: Optional[int] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    total_time_minutes: Optional[int] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    notes: Optional[str] = ""
    nutrition: Optional[dict] = {}
    rating: Optional[int] = 0
    is_favourite: Optional[bool] = False
    is_pinned: Optional[bool] = False
    photo_urls: Optional[list] = []
    category_ids: Optional[list] = []
    tag_ids: Optional[list] = []
    tag_names: Optional[list] = []

class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    ingredients: Optional[list] = None
    directions: Optional[list] = None
    servings: Optional[int] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    total_time_minutes: Optional[int] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    notes: Optional[str] = None
    nutrition: Optional[dict] = None
    rating: Optional[int] = None
    is_favourite: Optional[bool] = None
    is_pinned: Optional[bool] = None
    photo_urls: Optional[list] = None
    category_ids: Optional[list] = None
    tag_ids: Optional[list] = None
    tag_names: Optional[list] = None

@router.get("")
async def list_recipes(
    request: Request,
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    tag: Optional[str] = None,
    rating_min: Optional[int] = None,
    favourites: Optional[bool] = None,
    sort: Optional[str] = "updated_at",
    order: Optional[str] = "desc",
    limit: int = 50,
    offset: int = 0,
):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        query = "SELECT DISTINCT r.* FROM recipes r"
        joins = []
        conditions = ["r.user_id = ?"]
        params: list = [user["id"]]

        if category_id:
            joins.append("JOIN recipe_categories rc ON r.id = rc.recipe_id")
            conditions.append("rc.category_id = ?")
            params.append(category_id)
        if tag:
            joins.append("JOIN recipe_tags rt ON r.id = rt.recipe_id JOIN tags t ON rt.tag_id = t.id")
            conditions.append("t.name = ?")
            params.append(tag)
        if q:
            conditions.append("(r.title LIKE ? OR r.description LIKE ? OR r.ingredients LIKE ? OR r.directions LIKE ?)")
            pat = f"%{q}%"
            params.extend([pat, pat, pat, pat])
            await log_activity(user["id"], "search", {"query": q})
            await conn.execute("UPDATE users SET last_search = ?, updated_at = ? WHERE id = ?",
                               (q, datetime.now(timezone.utc).isoformat(), user["id"]))
            await conn.commit()
        if rating_min:
            conditions.append("r.rating >= ?")
            params.append(rating_min)
        if favourites:
            conditions.append("r.is_favourite = 1")

        allowed_sort = {"title", "created_at", "updated_at", "rating", "prep_time_minutes", "cook_time_minutes"}
        sort_col = sort if sort in allowed_sort else "updated_at"
        order_dir = "ASC" if order == "asc" else "DESC"

        full_query = f"{query} {' '.join(joins)} WHERE {' AND '.join(conditions)} ORDER BY r.{sort_col} {order_dir} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur = await conn.execute(full_query, params)
        recipes = [_row_dict(r) for r in await cur.fetchall()]

        count_query = f"SELECT COUNT(DISTINCT r.id) FROM recipes r {' '.join(joins)} WHERE {' AND '.join(conditions[:-0] if not conditions else conditions)}"
        count_params = params[:-2]
        cur2 = await conn.execute(
            f"SELECT COUNT(DISTINCT r.id) FROM recipes r {' '.join(joins)} WHERE {' AND '.join(conditions)}",
            count_params
        )
        total = (await cur2.fetchone())[0]

        for recipe in recipes:
            for field in ("ingredients", "directions", "photo_urls"):
                if recipe.get(field) and isinstance(recipe[field], str):
                    recipe[field] = json.loads(recipe[field])
            if recipe.get("nutrition") and isinstance(recipe["nutrition"], str):
                recipe["nutrition"] = json.loads(recipe["nutrition"])
            cur_c = await conn.execute(
                "SELECT c.id, c.name FROM categories c JOIN recipe_categories rc ON c.id = rc.category_id WHERE rc.recipe_id = ?",
                (recipe["id"],))
            recipe["categories"] = [_row_dict(c) for c in await cur_c.fetchall()]
            cur_t = await conn.execute(
                "SELECT t.id, t.name, t.type FROM tags t JOIN recipe_tags rt ON t.id = rt.tag_id WHERE rt.recipe_id = ?",
                (recipe["id"],))
            recipe["tags"] = [_row_dict(t) for t in await cur_t.fetchall()]

        return {"recipes": recipes, "total": total, "limit": limit, "offset": offset}
    finally:
        await conn.close()

@router.get("/{recipe_id}")
async def get_recipe(recipe_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT * FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user["id"]))
        recipe = await cur.fetchone()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        recipe = _row_dict(recipe)
        for field in ("ingredients", "directions", "photo_urls"):
            if recipe.get(field) and isinstance(recipe[field], str):
                recipe[field] = json.loads(recipe[field])
        if recipe.get("nutrition") and isinstance(recipe["nutrition"], str):
            recipe["nutrition"] = json.loads(recipe["nutrition"])

        cur_c = await conn.execute(
            "SELECT c.id, c.name FROM categories c JOIN recipe_categories rc ON c.id = rc.category_id WHERE rc.recipe_id = ?",
            (recipe_id,))
        recipe["categories"] = [_row_dict(c) for c in await cur_c.fetchall()]
        cur_t = await conn.execute(
            "SELECT t.id, t.name, t.type FROM tags t JOIN recipe_tags rt ON t.id = rt.tag_id WHERE rt.recipe_id = ?",
            (recipe_id,))
        recipe["tags"] = [_row_dict(t) for t in await cur_t.fetchall()]
        cur_l = await conn.execute(
            "SELECT r.id, r.title, rl.link_type FROM recipes r JOIN recipe_links rl ON r.id = rl.linked_recipe_id WHERE rl.recipe_id = ?",
            (recipe_id,))
        recipe["linked_recipes"] = [_row_dict(l) for l in await cur_l.fetchall()]
        return recipe
    finally:
        await conn.close()

@router.post("")
async def create_recipe(body: RecipeCreate, request: Request):
    user = await get_current_user(request)
    rid = f"rcp-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO recipes (id, user_id, title, description, ingredients, directions, servings,
               prep_time_minutes, cook_time_minutes, total_time_minutes, source_url, source_name,
               notes, nutrition, rating, is_favourite, is_pinned, photo_urls, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, user["id"], body.title, body.description or "",
             json.dumps(body.ingredients or []), json.dumps(body.directions or []),
             body.servings, body.prep_time_minutes, body.cook_time_minutes, body.total_time_minutes,
             body.source_url, body.source_name, body.notes or "",
             json.dumps(body.nutrition or {}), body.rating or 0,
             1 if body.is_favourite else 0, 1 if body.is_pinned else 0,
             json.dumps(body.photo_urls or []), now, now),
        )
        if body.category_ids:
            for cid in body.category_ids:
                await conn.execute("INSERT OR IGNORE INTO recipe_categories (recipe_id, category_id) VALUES (?,?)", (rid, cid))
        if body.tag_ids:
            for tid in body.tag_ids:
                await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (rid, tid))
        if body.tag_names:
            for tname in body.tag_names:
                tid = f"tag-{uuid.uuid4().hex[:8]}"
                await conn.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                   (tid, user["id"], tname, "custom"))
                cur = await conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?", (user["id"], tname))
                row = await cur.fetchone()
                if row:
                    await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (rid, row["id"]))

        await conn.commit()
        await log_activity(user["id"], "create_recipe", {"recipe_id": rid, "title": body.title})
        await conn.execute("UPDATE users SET upload_count = upload_count + 1, updated_at = ? WHERE id = ?",
                           (now, user["id"]))
        await conn.commit()
        return {"id": rid, "status": "created"}
    finally:
        await conn.close()

@router.put("/{recipe_id}")
async def update_recipe(recipe_id: str, body: RecipeUpdate, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT id FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user["id"]))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")

        updates = {}
        data = body.model_dump(exclude_none=True)
        for key, val in data.items():
            if key in ("category_ids", "tag_ids", "tag_names"):
                continue
            if key in ("ingredients", "directions", "photo_urls", "nutrition"):
                updates[key] = json.dumps(val)
            elif key in ("is_favourite", "is_pinned"):
                updates[key] = 1 if val else 0
            else:
                updates[key] = val

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [recipe_id]
            await conn.execute(f"UPDATE recipes SET {set_clause} WHERE id = ?", vals)

        if "category_ids" in data:
            await conn.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", (recipe_id,))
            for cid in data["category_ids"]:
                await conn.execute("INSERT INTO recipe_categories (recipe_id, category_id) VALUES (?,?)", (recipe_id, cid))

        if "tag_ids" in data:
            await conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
            for tid in data["tag_ids"]:
                await conn.execute("INSERT INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (recipe_id, tid))

        if "tag_names" in data:
            await conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
            for tname in data["tag_names"]:
                tid = f"tag-{uuid.uuid4().hex[:8]}"
                await conn.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                   (tid, user["id"], tname, "custom"))
                cur2 = await conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?", (user["id"], tname))
                row = await cur2.fetchone()
                if row:
                    await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (recipe_id, row["id"]))

        await conn.commit()
        return {"status": "updated"}
    finally:
        await conn.close()

@router.delete("/{recipe_id}")
async def delete_recipe(recipe_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT id FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user["id"]))
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")
        await conn.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", (recipe_id,))
        await conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
        await conn.execute("DELETE FROM recipe_links WHERE recipe_id = ? OR linked_recipe_id = ?", (recipe_id, recipe_id))
        await conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        await conn.commit()
        await log_activity(user["id"], "delete_recipe", {"recipe_id": recipe_id})
        return {"status": "deleted"}
    finally:
        await conn.close()

@router.post("/{recipe_id}/link/{linked_id}")
async def link_recipe(recipe_id: str, linked_id: str, request: Request, link_type: str = "related"):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("INSERT OR IGNORE INTO recipe_links (recipe_id, linked_recipe_id, link_type) VALUES (?,?,?)",
                           (recipe_id, linked_id, link_type))
        await conn.commit()
        return {"status": "linked"}
    finally:
        await conn.close()

@router.delete("/{recipe_id}/link/{linked_id}")
async def unlink_recipe(recipe_id: str, linked_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM recipe_links WHERE recipe_id = ? AND linked_recipe_id = ?", (recipe_id, linked_id))
        await conn.commit()
        return {"status": "unlinked"}
    finally:
        await conn.close()

@router.post("/{recipe_id}/photo")
async def upload_photo(recipe_id: str, request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request)
    if not user.get("can_upload", True):
        raise HTTPException(status_code=403, detail="Upload not permitted")
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT photo_urls FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user["id"]))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recipe not found")

        upload_dir = Path(get_upload_dir()) / user["id"]
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
        fname = f"{uuid.uuid4().hex[:12]}{ext}"
        fpath = upload_dir / fname
        content = await file.read()
        fpath.write_bytes(content)

        photos = json.loads(row["photo_urls"] or "[]")
        photo_url = f"/uploads/{user['id']}/{fname}"
        photos.append(photo_url)
        await conn.execute("UPDATE recipes SET photo_urls = ?, updated_at = ? WHERE id = ?",
                           (json.dumps(photos), datetime.now(timezone.utc).isoformat(), recipe_id))
        await conn.commit()
        return {"url": photo_url, "status": "uploaded"}
    finally:
        await conn.close()
