import json
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from app.auth import get_current_user
from app.database import get_conn, _row_dict
from app.services.scaler import scale_ingredients, convert_recipe_units
from app.services.importer import import_from_url
from app.services.enrichment import enrich_recipe
from app.services.ocr import analyze_recipe_image
from app.auth import log_activity
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api", tags=["cooking"])

class ImportRequest(BaseModel):
    url: str
    auto_save: Optional[bool] = False
    force_save: Optional[bool] = False  # Skip duplicate check
    replace_id: Optional[str] = None    # Replace an existing recipe instead of creating new

@router.get("/recipes/{recipe_id}/cook")
async def get_cooking_data(recipe_id: str, request: Request, servings: Optional[int] = None, units: Optional[str] = None):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT * FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user["id"]))
        recipe = await cur.fetchone()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        recipe = _row_dict(recipe)
        ingredients = json.loads(recipe.get("ingredients") or "[]")
        directions = json.loads(recipe.get("directions") or "[]")
        original_servings = recipe.get("servings")

        if servings and original_servings:
            ingredients = scale_ingredients(ingredients, original_servings, servings)
        if units in ("metric", "imperial"):
            ingredients = convert_recipe_units(ingredients, units)

        timers = []
        for d in directions:
            if d.get("timer_minutes"):
                timers.append({
                    "step": d["step"],
                    "minutes": d["timer_minutes"],
                    "label": f"Step {d['step']}",
                })

        return {
            "recipe_id": recipe_id,
            "title": recipe["title"],
            "ingredients": ingredients,
            "directions": directions,
            "servings": servings or original_servings,
            "original_servings": original_servings,
            "timers": timers,
            "photo_urls": json.loads(recipe.get("photo_urls") or "[]"),
            "notes": recipe.get("notes", ""),
        }
    finally:
        await conn.close()

@router.post("/import")
async def import_recipe(body: ImportRequest, request: Request):
    user = await get_current_user(request)
    if not user.get("can_upload", True):
        raise HTTPException(status_code=403, detail="Upload not permitted for this account")
    try:
        data = await import_from_url(body.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import: {str(e)}")

    await log_activity(user["id"], "import", {"url": body.url, "title": data.get("title", "")})

    # Check for duplicates before saving (unless force_save)
    if body.auto_save and not body.force_save:
        from app.services.duplicate_detector import find_duplicates
        duplicates = await find_duplicates(data, user["id"], threshold=0.55)
        if duplicates:
            # Return the imported data + duplicates for the UI to handle
            data["saved"] = False
            data["duplicates"] = duplicates
            data["duplicate_action_required"] = True
            return data

    if body.auto_save or body.force_save:
        rid = await _save_imported_recipe(data, user, replace_id=body.replace_id)
        data["id"] = rid
        data["saved"] = True
        data["duplicate_action_required"] = False
    else:
        data["saved"] = False
        enriched = await enrich_recipe(data, force_tags=True)
        if enriched:
            data["enriched"] = enriched

    return data


async def _save_imported_recipe(data: dict, user: dict, replace_id: str = None) -> str:
    """Save an imported recipe, optionally replacing an existing one."""
    now = datetime.now(timezone.utc).isoformat()
    conn = await get_conn()
    try:
        if replace_id:
            # Delete the old recipe first
            await conn.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", (replace_id,))
            await conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (replace_id,))
            await conn.execute("DELETE FROM recipe_links WHERE recipe_id = ? OR linked_recipe_id = ?", (replace_id, replace_id))
            await conn.execute("DELETE FROM recipes WHERE id = ? AND user_id = ?", (replace_id, user["id"]))
            await conn.commit()

        rid = f"rcp-{uuid.uuid4().hex[:12]}"
        await conn.execute(
            """INSERT INTO recipes (id, user_id, title, description, ingredients, directions, servings,
               prep_time_minutes, cook_time_minutes, total_time_minutes, source_url, source_name,
               notes, nutrition, photo_urls, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (rid, user["id"], data["title"], data.get("description", ""),
             json.dumps(data.get("ingredients", [])), json.dumps(data.get("directions", [])),
             data.get("servings"), data.get("prep_time_minutes"), data.get("cook_time_minutes"),
             data.get("total_time_minutes"), data.get("source_url"), data.get("source_name"),
             "", json.dumps(data.get("nutrition", {})),
             json.dumps(data.get("photo_urls", [])), now, now),
        )
        await conn.execute("UPDATE users SET upload_count = upload_count + 1, updated_at = ? WHERE id = ?",
                           (now, user["id"]))
        await conn.commit()

        enriched = await enrich_recipe(data, force_tags=True)
        if enriched:
            updates = {}
            if enriched.get("description") and not data.get("description"):
                updates["description"] = enriched["description"]
            if enriched.get("nutrition"):
                updates["nutrition"] = json.dumps(enriched["nutrition"])
            if enriched.get("prep_time_minutes") and not data.get("prep_time_minutes"):
                updates["prep_time_minutes"] = enriched["prep_time_minutes"]
            if enriched.get("cook_time_minutes") and not data.get("cook_time_minutes"):
                updates["cook_time_minutes"] = enriched["cook_time_minutes"]
            if enriched.get("total_time_minutes") and not data.get("total_time_minutes"):
                updates["total_time_minutes"] = enriched["total_time_minutes"]
            if updates:
                updates["updated_at"] = now
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                vals = list(updates.values()) + [rid]
                await conn.execute(f"UPDATE recipes SET {set_clause} WHERE id = ?", vals)
                await conn.commit()

            if enriched.get("suggested_tags"):
                for tname in enriched["suggested_tags"]:
                    tid = f"tag-{uuid.uuid4().hex[:8]}"
                    await conn.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                       (tid, user["id"], tname, "auto"))
                    cur = await conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?",
                                             (user["id"], tname))
                    row = await cur.fetchone()
                    if row:
                        await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)",
                                           (rid, row["id"]))
                await conn.commit()

        return rid
    finally:
        await conn.close()


@router.post("/check-duplicate")
async def check_duplicate(request: Request):
    """Check if a recipe (by title and ingredients) has duplicates in the user's collection."""
    user = await get_current_user(request)
    body = await request.json()
    from app.services.duplicate_detector import find_duplicates
    duplicates = await find_duplicates(body, user["id"], threshold=0.55)
    return {"duplicates": duplicates, "has_duplicates": len(duplicates) > 0}

@router.post("/analyze-image")
async def analyze_image(request: Request, file: UploadFile = File(...)):
    """Analyze a recipe image (photo of cookbook, handwritten card, or plated dish) using Claude Vision."""
    user = await get_current_user(request)
    if not user.get("can_upload", True):
        raise HTTPException(status_code=403, detail="Upload not permitted")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 20MB)")

    content_type = file.content_type or "image/jpeg"
    await log_activity(user["id"], "ocr_analyze", {"filename": file.filename, "size": len(content)})

    result = await analyze_recipe_image(content, content_type)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    # Save the uploaded image so it can be used as the recipe photo
    from pathlib import Path
    from app.config import get_upload_dir
    upload_dir = Path(get_upload_dir()) / user["id"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    fname = f"{uuid.uuid4().hex[:12]}{ext}"
    fpath = upload_dir / fname
    fpath.write_bytes(content)
    photo_url = f"/uploads/{user['id']}/{fname}"

    # Attach the uploaded image as the recipe photo
    if not result.get("photo_urls"):
        result["photo_urls"] = []
    result["photo_urls"].insert(0, photo_url)

    return result


@router.post("/recipes/{recipe_id}/enrich")
async def enrich_existing(recipe_id: str, request: Request):
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT * FROM recipes WHERE id = ? AND user_id = ?", (recipe_id, user["id"]))
        recipe = await cur.fetchone()
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        recipe = _row_dict(recipe)
        recipe["ingredients"] = json.loads(recipe.get("ingredients") or "[]")
        recipe["directions"] = json.loads(recipe.get("directions") or "[]")
        recipe["nutrition"] = json.loads(recipe.get("nutrition") or "{}")

        # Get existing tags
        cur_t = await conn.execute(
            "SELECT t.name FROM tags t JOIN recipe_tags rt ON t.id = rt.tag_id WHERE rt.recipe_id = ?",
            (recipe_id,))
        recipe["tags"] = [_row_dict(t)["name"] for t in await cur_t.fetchall()]

        enriched = await enrich_recipe(recipe, force_tags=True)
        if not enriched:
            return {"status": "no_changes", "message": "Nothing to enrich or AI not configured. Set ANTHROPIC_API_KEY environment variable."}

        updates = {}
        if enriched.get("description") and not recipe.get("description"):
            updates["description"] = enriched["description"]
        if enriched.get("nutrition") and (not recipe.get("nutrition") or recipe["nutrition"] == {}):
            updates["nutrition"] = json.dumps(enriched["nutrition"])
        if enriched.get("prep_time_minutes") and not recipe.get("prep_time_minutes"):
            updates["prep_time_minutes"] = enriched["prep_time_minutes"]
        if enriched.get("cook_time_minutes") and not recipe.get("cook_time_minutes"):
            updates["cook_time_minutes"] = enriched["cook_time_minutes"]
        if enriched.get("total_time_minutes") and not recipe.get("total_time_minutes"):
            updates["total_time_minutes"] = enriched["total_time_minutes"]

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [recipe_id]
            await conn.execute(f"UPDATE recipes SET {set_clause} WHERE id = ?", vals)
            await conn.commit()

        tags_added = []
        if enriched.get("suggested_tags"):
            for tname in enriched["suggested_tags"]:
                tid = f"tag-{uuid.uuid4().hex[:8]}"
                await conn.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                   (tid, user["id"], tname, "auto"))
                cur2 = await conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?", (user["id"], tname))
                row = await cur2.fetchone()
                if row:
                    await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)",
                                       (recipe_id, row["id"]))
                    tags_added.append(tname)
            await conn.commit()

        return {"status": "enriched", "fields_updated": list(updates.keys()), "tags_added": tags_added, "enriched": enriched}
    finally:
        await conn.close()

@router.post("/recipes/enrich-all")
async def enrich_all_recipes(request: Request):
    """Enrich all recipes for the current user with AI-generated tags and missing fields."""
    user = await get_current_user(request)
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=400, detail="ANTHROPIC_API_KEY not set. Configure it as an environment variable.")

    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT id, title FROM recipes WHERE user_id = ?", (user["id"],))
        all_recipes = [_row_dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    results = []
    for r in all_recipes:
        try:
            # Re-fetch full recipe for each enrichment
            conn2 = await get_conn()
            try:
                cur2 = await conn2.execute("SELECT * FROM recipes WHERE id = ?", (r["id"],))
                recipe = _row_dict(await cur2.fetchone())
                recipe["ingredients"] = json.loads(recipe.get("ingredients") or "[]")
                recipe["directions"] = json.loads(recipe.get("directions") or "[]")
                recipe["nutrition"] = json.loads(recipe.get("nutrition") or "{}")
                cur_t = await conn2.execute(
                    "SELECT t.name FROM tags t JOIN recipe_tags rt ON t.id = rt.tag_id WHERE rt.recipe_id = ?",
                    (r["id"],))
                recipe["tags"] = [_row_dict(t)["name"] for t in await cur_t.fetchall()]
            finally:
                await conn2.close()

            enriched = await enrich_recipe(recipe, force_tags=True)
            if not enriched:
                results.append({"id": r["id"], "title": r["title"], "status": "skipped"})
                continue

            conn3 = await get_conn()
            try:
                updates = {}
                if enriched.get("description") and not recipe.get("description"):
                    updates["description"] = enriched["description"]
                if enriched.get("nutrition") and (not recipe.get("nutrition") or recipe["nutrition"] == {}):
                    updates["nutrition"] = json.dumps(enriched["nutrition"])
                if enriched.get("prep_time_minutes") and not recipe.get("prep_time_minutes"):
                    updates["prep_time_minutes"] = enriched["prep_time_minutes"]
                if enriched.get("cook_time_minutes") and not recipe.get("cook_time_minutes"):
                    updates["cook_time_minutes"] = enriched["cook_time_minutes"]
                if enriched.get("total_time_minutes") and not recipe.get("total_time_minutes"):
                    updates["total_time_minutes"] = enriched["total_time_minutes"]

                if updates:
                    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    vals = list(updates.values()) + [r["id"]]
                    await conn3.execute(f"UPDATE recipes SET {set_clause} WHERE id = ?", vals)
                    await conn3.commit()

                tags_added = []
                if enriched.get("suggested_tags"):
                    for tname in enriched["suggested_tags"]:
                        tid = f"tag-{uuid.uuid4().hex[:8]}"
                        await conn3.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                           (tid, user["id"], tname, "auto"))
                        cur3 = await conn3.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?",
                                                   (user["id"], tname))
                        row = await cur3.fetchone()
                        if row:
                            await conn3.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)",
                                               (r["id"], row["id"]))
                            tags_added.append(tname)
                    await conn3.commit()

                results.append({
                    "id": r["id"],
                    "title": r["title"],
                    "status": "enriched",
                    "fields_updated": list(updates.keys()),
                    "tags_added": tags_added,
                })
            finally:
                await conn3.close()
        except Exception as e:
            results.append({"id": r["id"], "title": r["title"], "status": "error", "error": str(e)})

    await log_activity(user["id"], "enrich_all", {"recipes_processed": len(results)})
    return {"status": "complete", "results": results, "total": len(results)}
