import json
import os
import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user, log_activity
from app.database import get_conn, _row_dict
from app.config import get_ai_config


def _repair_truncated_json(text: str) -> str:
    """Attempt to repair JSON that was truncated mid-stream by closing open brackets/braces."""
    text = text.rstrip()
    # Remove any trailing comma
    text = text.rstrip(',').rstrip()
    # Count open/close braces and brackets
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    # Check if we're inside a string (odd number of unescaped quotes after last structure)
    # Simple heuristic: if the last non-whitespace char isn't a structural char, close the string
    last = text.rstrip()[-1] if text.rstrip() else ''
    if last not in ('}', ']', '"', ',', ':'):
        text += '"'
    # Close any open strings that look like they're in the middle of a value
    # Remove trailing incomplete key-value pairs
    text = re.sub(r',\s*"[^"]*$', '', text)
    text = re.sub(r',\s*$', '', text)
    # Close brackets then braces
    text += ']' * max(0, open_brackets)
    text += '}' * max(0, open_braces)
    return text

router = APIRouter(prefix="/api/menu", tags=["menu"])

class MenuRequest(BaseModel):
    num_courses: int = 3
    cuisine: Optional[str] = None
    max_duration_minutes: Optional[int] = None
    guests: Optional[int] = 4
    dietary: Optional[list] = None
    occasion: Optional[str] = None
    difficulty: Optional[str] = None  # easy, medium, advanced
    use_pantry: Optional[list] = None  # ingredients to use
    avoid_ingredients: Optional[list] = None
    notes: Optional[str] = None

class IngredientSearchRequest(BaseModel):
    ingredients: list
    match_all: Optional[bool] = False

@router.post("/generate")
async def generate_menu(body: MenuRequest, request: Request):
    user = await get_current_user(request)
    ai_config = get_ai_config()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="AI not configured. Set ANTHROPIC_API_KEY environment variable.")

    # Build context from user's existing recipes
    conn = await get_conn()
    try:
        cur = await conn.execute(
            "SELECT title, description, ingredients, prep_time_minutes, cook_time_minutes, total_time_minutes FROM recipes WHERE user_id = ? LIMIT 50",
            (user["id"],))
        existing = [_row_dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    existing_titles = [r["title"] for r in existing] if existing else []

    # Build the prompt
    filters = []
    if body.cuisine:
        filters.append(f"Cuisine/inspiration: {body.cuisine}")
    if body.max_duration_minutes:
        filters.append(f"Maximum total cooking time: {body.max_duration_minutes} minutes (total for all courses combined)")
    if body.guests:
        filters.append(f"Number of guests: {body.guests}")
    if body.dietary:
        filters.append(f"Dietary requirements: {', '.join(body.dietary)}")
    if body.occasion:
        filters.append(f"Occasion: {body.occasion}")
    if body.difficulty:
        filters.append(f"Difficulty level: {body.difficulty}")
    if body.use_pantry:
        filters.append(f"Try to incorporate these ingredients: {', '.join(body.use_pantry)}")
    if body.avoid_ingredients:
        filters.append(f"Avoid these ingredients: {', '.join(body.avoid_ingredients)}")
    if body.notes:
        filters.append(f"Additional notes: {body.notes}")

    filter_text = "\n".join(f"- {f}" for f in filters) if filters else "No specific filters."

    existing_context = ""
    if existing_titles:
        existing_context = f"\nThe user already has these recipes in their collection: {', '.join(existing_titles[:20])}. You may suggest some of these if they fit, but also suggest new ones."

    prompt = f"""Create a {body.num_courses}-course menu. {filter_text} {existing_context}

Return ONLY a JSON object (no markdown, no explanation). Be BRIEF — this is critical.

{{"menu_title":"name","description":"1 sentence","total_estimated_time_minutes":N,"courses":[{{"course_name":"Starter","recipe":{{"title":"name","description":"1 sentence","servings":{body.guests or 4},"prep_time_minutes":N,"cook_time_minutes":N,"total_time_minutes":N,"ingredients":[{{"qty":"1","unit":"cup","name":"ingredient","note":"","group":""}}],"directions":[{{"step":1,"text":"Do this.","timer_minutes":null}}],"nutrition":{{"calories":N,"protein":N,"carbs":N,"fat":N,"fiber":N}},"suggested_tags":["tag1","tag2"]}},"wine_pairing":"wine","plating_tip":"tip"}}],"shopping_summary":["item1"],"timeline":"1 sentence"}}

STRICT LIMITS per recipe:
- Max 8 ingredients, short names
- Max 4 directions, 1 short sentence each
- Max 4 tags
- Omit "note" and "group" if empty (use "")
- No markdown, no code fences, just the raw JSON object"""

    try:
        import anthropic
        import re
        import asyncio as _asyncio
        client = anthropic.AsyncAnthropic(api_key=api_key)

        # Try models in order of preference
        models = [
            ai_config.get("model", "claude-sonnet-4-20250514"),
            "claude-sonnet-4-20250514",
            "claude-sonnet-4-6",
        ]
        seen = set()
        models = [m for m in models if m not in seen and not seen.add(m)]

        response_text = None
        last_error = None
        # Retry up to 3 times total (handles 529 overload)
        for attempt in range(3):
            for model in models:
                try:
                    message = await client.messages.create(
                        model=model,
                        max_tokens=16000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    response_text = message.content[0].text
                    # Check if response was truncated (stop_reason != "end_turn")
                    if message.stop_reason != "end_turn":
                        print(f"[MAZARINE] Warning: response truncated (stop_reason={message.stop_reason})")
                        # Try to close any unclosed JSON
                        response_text = _repair_truncated_json(response_text)
                    break
                except Exception as model_err:
                    last_error = model_err
                    err_str = str(model_err)
                    print(f"[MAZARINE] Model {model} attempt {attempt+1} failed: {err_str[:100]}")
                    # Retry on overload (529)
                    if "529" in err_str or "overloaded" in err_str.lower():
                        await _asyncio.sleep(2 * (attempt + 1))
                    continue
            if response_text:
                break

        if not response_text:
            raise HTTPException(
                status_code=500,
                detail=f"All AI models failed. Last error: {str(last_error)}. Check your ANTHROPIC_API_KEY is valid."
            )

        # Extract JSON from response
        json_text = response_text
        if "```" in response_text:
            m = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL)
            if m:
                json_text = m.group(1)

        # Try to find JSON object in the response
        json_text = json_text.strip()
        if not json_text.startswith("{"):
            # Try to find the first { in the response
            idx = json_text.find("{")
            if idx >= 0:
                json_text = json_text[idx:]
            else:
                raise HTTPException(status_code=500, detail="AI response did not contain valid JSON. Please try again.")

        menu = json.loads(json_text)

        await log_activity(user["id"], "menu_generate", {
            "courses": body.num_courses,
            "cuisine": body.cuisine,
            "title": menu.get("menu_title", ""),
        })

        return menu

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON. Please try again. ({str(e)[:80]})")
    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "401" in error_msg:
            raise HTTPException(status_code=500, detail="Invalid ANTHROPIC_API_KEY. Check your API key in settings.")
        raise HTTPException(status_code=500, detail=f"Menu generation failed: {error_msg[:150]}")

@router.post("/save")
async def save_menu_recipes(request: Request):
    """Save selected recipes from a generated menu with duplicate check, AI enrichment, and photo search."""
    user = await get_current_user(request)
    body = await request.json()
    courses = body.get("courses", [])
    menu_title = body.get("menu_title", "Menu")
    results = []

    from app.services.photo_finder import find_recipe_photo
    from app.services.enrichment import enrich_recipe
    from app.services.duplicate_detector import find_duplicates

    for course in courses:
        recipe = course.get("recipe", {})
        if not recipe.get("title"):
            continue

        # 1. Check for duplicates
        duplicates = await find_duplicates(recipe, user["id"], threshold=0.55)
        if duplicates:
            best_match = duplicates[0]
            results.append({
                "title": recipe["title"],
                "course": course.get("course_name", ""),
                "status": "duplicate",
                "match": best_match,
                "new_recipe": recipe,
            })
            continue

        # 2. Enrich with AI (fill any missing fields, add tags)
        enriched = await enrich_recipe(recipe, force_tags=True)
        if enriched:
            if enriched.get("nutrition") and not recipe.get("nutrition"):
                recipe["nutrition"] = enriched["nutrition"]
            if enriched.get("description") and not recipe.get("description"):
                recipe["description"] = enriched["description"]
            extra_tags = enriched.get("suggested_tags", [])
            existing_tags = recipe.get("suggested_tags", [])
            recipe["suggested_tags"] = list(set(existing_tags + extra_tags))

        # 3. Find a photo
        photo_url = await find_recipe_photo(recipe["title"])
        photo_urls = [photo_url] if photo_url else []

        # 4. Build notes
        notes_parts = [f"Part of menu: {menu_title}"]
        if course.get("course_name"):
            notes_parts.append(f"Course: {course['course_name']}")
        if course.get("wine_pairing"):
            notes_parts.append(f"Wine pairing: {course['wine_pairing']}")
        if course.get("plating_tip"):
            notes_parts.append(f"Plating: {course['plating_tip']}")

        # 5. Save to database
        rid = f"rcp-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        conn = await get_conn()
        try:
            await conn.execute(
                """INSERT INTO recipes (id, user_id, title, description, ingredients, directions, servings,
                   prep_time_minutes, cook_time_minutes, total_time_minutes, notes, nutrition, photo_urls,
                   rating, is_favourite, is_pinned, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, user["id"], recipe["title"], recipe.get("description", ""),
                 json.dumps(recipe.get("ingredients", [])), json.dumps(recipe.get("directions", [])),
                 recipe.get("servings"), recipe.get("prep_time_minutes"), recipe.get("cook_time_minutes"),
                 recipe.get("total_time_minutes"), "\n".join(notes_parts),
                 json.dumps(recipe.get("nutrition", {})), json.dumps(photo_urls),
                 0, 0, 0, now, now),
            )

            # Add tags
            tags_added = []
            for tname in recipe.get("suggested_tags", []):
                tid = f"tag-{uuid.uuid4().hex[:8]}"
                await conn.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                   (tid, user["id"], tname, "auto"))
                cur = await conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?", (user["id"], tname))
                row = await cur.fetchone()
                if row:
                    await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (rid, row["id"]))
                    tags_added.append(tname)

            await conn.commit()

            results.append({
                "id": rid,
                "title": recipe["title"],
                "course": course.get("course_name", ""),
                "status": "saved",
                "photo": photo_urls[0] if photo_urls else None,
                "tags": tags_added,
            })
        finally:
            await conn.close()

    # Link all saved recipes together
    saved_items = [r for r in results if r.get("id")]
    if len(saved_items) > 1:
        conn = await get_conn()
        try:
            for i, item in enumerate(saved_items):
                for j, other in enumerate(saved_items):
                    if i != j:
                        await conn.execute(
                            "INSERT OR IGNORE INTO recipe_links (recipe_id, linked_recipe_id, link_type) VALUES (?,?,?)",
                            (item["id"], other["id"], "menu"))
            await conn.commit()
        finally:
            await conn.close()

    await log_activity(user["id"], "menu_save", {"menu": menu_title, "recipes": len(saved_items)})
    return {"status": "saved", "recipes": results}


@router.post("/search-by-ingredient")
async def search_by_ingredient(body: IngredientSearchRequest, request: Request):
    """Search recipes that contain specific ingredients."""
    user = await get_current_user(request)
    conn = await get_conn()
    try:
        cur = await conn.execute("SELECT * FROM recipes WHERE user_id = ?", (user["id"],))
        all_recipes = [_row_dict(r) for r in await cur.fetchall()]

        search_terms = [ing.lower().strip() for ing in body.ingredients if ing.strip()]
        results = []

        for recipe in all_recipes:
            ingredients = json.loads(recipe.get("ingredients") or "[]")
            ingredient_names = [i.get("name", "").lower() for i in ingredients]
            ingredient_text = " ".join(ingredient_names)

            if body.match_all:
                matched = all(any(term in name for name in ingredient_names) for term in search_terms)
            else:
                matched = any(any(term in name for name in ingredient_names) for term in search_terms)

            if matched:
                # Count how many search terms match
                match_count = sum(1 for term in search_terms if any(term in name for name in ingredient_names))
                for field in ("ingredients", "directions", "photo_urls"):
                    if recipe.get(field) and isinstance(recipe[field], str):
                        recipe[field] = json.loads(recipe[field])
                if recipe.get("nutrition") and isinstance(recipe["nutrition"], str):
                    recipe["nutrition"] = json.loads(recipe["nutrition"])

                # Add tags
                cur_t = await conn.execute(
                    "SELECT t.id, t.name, t.type FROM tags t JOIN recipe_tags rt ON t.id = rt.tag_id WHERE rt.recipe_id = ?",
                    (recipe["id"],))
                recipe["tags"] = [_row_dict(t) for t in await cur_t.fetchall()]
                recipe["_match_count"] = match_count
                recipe["_matched_ingredients"] = [term for term in search_terms if any(term in name for name in ingredient_names)]
                results.append(recipe)

        # Sort by match count descending
        results.sort(key=lambda r: r["_match_count"], reverse=True)

        await log_activity(user["id"], "ingredient_search", {"ingredients": body.ingredients, "results": len(results)})

        return {"recipes": results, "total": len(results), "searched_ingredients": search_terms}
    finally:
        await conn.close()


class WebSearchRequest(BaseModel):
    query: str

class WebSaveRequest(BaseModel):
    recipes: list  # List of recipe dicts from web search results


@router.post("/web-search")
async def web_recipe_search(body: WebSearchRequest, request: Request):
    """Search the web for recipes using Claude AI, return structured results with photos."""
    user = await get_current_user(request)
    ai_config = get_ai_config()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="AI not configured. Set ANTHROPIC_API_KEY.")

    await log_activity(user["id"], "web_search", {"query": body.query})

    prompt = f"""Search your knowledge for recipes matching: "{body.query}"

Return exactly 8 diverse recipe suggestions as a JSON array. Each recipe should be a real, well-known recipe.

Return ONLY a JSON array (no markdown, no explanation):
[
  {{
    "title": "Recipe Name",
    "description": "2-3 sentence appetising description",
    "cuisine": "Italian",
    "difficulty": "easy",
    "total_time_minutes": 30,
    "servings": 4,
    "key_ingredients": ["ingredient1", "ingredient2", "ingredient3"],
    "tags": ["tag1", "tag2"],
    "source_attribution": "Inspired by traditional recipe"
  }}
]

Rules:
- 8 results, diverse cuisines and styles
- Real dishes that exist, not invented ones
- Descriptions should be appetising and specific
- Include a mix of difficulties (easy, medium, advanced)
- Tags: cuisine, dietary, meal type (max 4)
- key_ingredients: 3-5 main ingredients only"""

    try:
        import anthropic
        import asyncio as _asyncio
        client = anthropic.AsyncAnthropic(api_key=api_key)

        models = [
            ai_config.get("model", "claude-sonnet-4-20250514"),
            "claude-sonnet-4-20250514",
            "claude-sonnet-4-6",
        ]
        seen_m = set()
        models = [m for m in models if m not in seen_m and not seen_m.add(m)]

        response_text = None
        for attempt in range(3):
            for model in models:
                try:
                    message = await client.messages.create(
                        model=model, max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    response_text = message.content[0].text
                    break
                except Exception as e:
                    if "529" in str(e):
                        await _asyncio.sleep(2 * (attempt + 1))
                    continue
            if response_text:
                break

        if not response_text:
            raise HTTPException(status_code=500, detail="AI search failed. Please try again.")

        # Parse JSON
        json_text = response_text.strip()
        if "```" in json_text:
            m = re.search(r"```(?:json)?\s*(.*?)```", json_text, re.DOTALL)
            if m:
                json_text = m.group(1).strip()
        if not json_text.startswith("["):
            idx = json_text.find("[")
            if idx >= 0:
                json_text = json_text[idx:]

        results = json.loads(json_text)

        # Find Pexels photos for each result
        from app.services.photo_finder import find_recipe_photo
        for r in results:
            photo = await find_recipe_photo(r.get("title", ""))
            r["photo_url"] = photo

        return {"results": results, "query": body.query, "total": len(results)}

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid results. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)[:100]}")


@router.post("/web-search/preview")
async def web_recipe_preview(request: Request):
    """Get full recipe details for selected web search results using AI."""
    user = await get_current_user(request)
    body = await request.json()
    titles = body.get("titles", [])
    if not titles or len(titles) > 4:
        raise HTTPException(status_code=400, detail="Select 1-4 recipes to preview")

    ai_config = get_ai_config()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="AI not configured.")

    titles_str = "\n".join(f"- {t}" for t in titles)
    prompt = f"""Create complete, detailed recipes for these dishes:
{titles_str}

Return ONLY a JSON array with full recipe details for each:
[
  {{
    "title": "Recipe Name",
    "description": "1-2 sentence description",
    "servings": 4,
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "total_time_minutes": 45,
    "ingredients": [{{"qty": "1", "unit": "cup", "name": "ingredient", "note": "", "group": ""}}],
    "directions": [{{"step": 1, "text": "Direction text.", "timer_minutes": null}}],
    "nutrition": {{"calories": 400, "protein": 25, "carbs": 40, "fat": 15, "fiber": 5}},
    "suggested_tags": ["cuisine", "dietary", "type", "characteristic"]
  }}
]

Max 8 ingredients, max 5 directions per recipe. Be concise."""

    try:
        import anthropic
        import asyncio as _asyncio
        client = anthropic.AsyncAnthropic(api_key=api_key)

        models = [ai_config.get("model", "claude-sonnet-4-20250514"), "claude-sonnet-4-6"]
        seen_m = set()
        models = [m for m in models if m not in seen_m and not seen_m.add(m)]

        response_text = None
        for attempt in range(3):
            for model in models:
                try:
                    message = await client.messages.create(
                        model=model, max_tokens=8000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    response_text = message.content[0].text
                    break
                except Exception as e:
                    if "529" in str(e):
                        await _asyncio.sleep(2 * (attempt + 1))
                    continue
            if response_text:
                break

        if not response_text:
            raise HTTPException(status_code=500, detail="AI failed. Try again.")

        json_text = response_text.strip()
        if "```" in json_text:
            m = re.search(r"```(?:json)?\s*(.*?)```", json_text, re.DOTALL)
            if m:
                json_text = m.group(1).strip()
        if not json_text.startswith("["):
            idx = json_text.find("[")
            if idx >= 0:
                json_text = json_text[idx:]

        recipes = json.loads(json_text)

        # Add photos
        from app.services.photo_finder import find_recipe_photo
        for r in recipes:
            r["photo_url"] = await find_recipe_photo(r.get("title", ""))

        return {"recipes": recipes}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)[:100]}")


@router.post("/web-search/save")
async def save_web_recipes(body: WebSaveRequest, request: Request):
    """Save recipes from web search to the collection with AI enrichment + duplicate check + photos."""
    user = await get_current_user(request)
    from app.services.enrichment import enrich_recipe
    from app.services.duplicate_detector import find_duplicates
    from app.services.photo_finder import find_recipe_photo

    results = []
    for recipe in body.recipes:
        if not recipe.get("title"):
            continue

        # 1. Duplicate check
        duplicates = await find_duplicates(recipe, user["id"], threshold=0.55)
        if duplicates:
            results.append({
                "title": recipe["title"], "status": "duplicate",
                "match": duplicates[0], "new_recipe": recipe,
            })
            continue

        # 2. AI enrichment
        enriched = await enrich_recipe(recipe, force_tags=True)
        if enriched:
            if enriched.get("nutrition") and not recipe.get("nutrition"):
                recipe["nutrition"] = enriched["nutrition"]
            if enriched.get("description") and not recipe.get("description"):
                recipe["description"] = enriched["description"]
            extra = enriched.get("suggested_tags", [])
            existing = recipe.get("suggested_tags", [])
            recipe["suggested_tags"] = list(set(existing + extra))

        # 3. Photo
        photo_url = recipe.get("photo_url") or await find_recipe_photo(recipe["title"])
        photo_urls = [photo_url] if photo_url else []

        # 4. Save
        rid = f"rcp-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        conn = await get_conn()
        try:
            await conn.execute(
                """INSERT INTO recipes (id, user_id, title, description, ingredients, directions, servings,
                   prep_time_minutes, cook_time_minutes, total_time_minutes, notes, nutrition, photo_urls,
                   rating, is_favourite, is_pinned, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, user["id"], recipe["title"], recipe.get("description", ""),
                 json.dumps(recipe.get("ingredients", [])), json.dumps(recipe.get("directions", [])),
                 recipe.get("servings"), recipe.get("prep_time_minutes"), recipe.get("cook_time_minutes"),
                 recipe.get("total_time_minutes"), recipe.get("source_attribution", ""),
                 json.dumps(recipe.get("nutrition", {})), json.dumps(photo_urls),
                 0, 0, 0, now, now),
            )
            tags_added = []
            for tname in recipe.get("suggested_tags", []):
                tid = f"tag-{uuid.uuid4().hex[:8]}"
                await conn.execute("INSERT OR IGNORE INTO tags (id, user_id, name, type) VALUES (?,?,?,?)",
                                   (tid, user["id"], tname, "auto"))
                cur = await conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?", (user["id"], tname))
                row = await cur.fetchone()
                if row:
                    await conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (rid, row["id"]))
                    tags_added.append(tname)
            await conn.commit()
            results.append({"id": rid, "title": recipe["title"], "status": "saved", "tags": tags_added, "photo": photo_urls[0] if photo_urls else None})
        finally:
            await conn.close()

    await log_activity(user["id"], "web_save", {"recipes": len([r for r in results if r.get("status") == "saved"])})
    return {"status": "saved", "recipes": results}
