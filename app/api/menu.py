import json
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user, log_activity
from app.database import get_conn, _row_dict
from app.config import get_ai_config

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

    prompt = f"""Create a complete menu with exactly {body.num_courses} courses.

Filters:
{filter_text}
{existing_context}

Return ONLY valid JSON with this structure:
{{
  "menu_title": "A creative name for this menu",
  "description": "1-2 sentence description of the menu concept",
  "total_estimated_time_minutes": <number>,
  "courses": [
    {{
      "course_name": "e.g. Starter, Main, Dessert, Amuse-bouche, Soup, Fish, Cheese",
      "recipe": {{
        "title": "Recipe name",
        "description": "1-2 sentence description",
        "servings": {body.guests or 4},
        "prep_time_minutes": <number>,
        "cook_time_minutes": <number>,
        "total_time_minutes": <number>,
        "ingredients": [
          {{"qty": "amount", "unit": "unit", "name": "ingredient", "note": "", "group": ""}}
        ],
        "directions": [
          {{"step": 1, "text": "direction text", "timer_minutes": null}}
        ],
        "nutrition": {{"calories": <number>, "protein": <grams>, "carbs": <grams>, "fat": <grams>, "fiber": <grams>}},
        "suggested_tags": ["tag1", "tag2"]
      }},
      "wine_pairing": "Optional wine suggestion",
      "plating_tip": "Brief plating or presentation suggestion"
    }}
  ],
  "shopping_summary": ["ingredient 1", "ingredient 2"],
  "timeline": "Suggested preparation timeline, e.g. what to prep first"
}}

Be creative, specific with quantities, and ensure the menu is cohesive. Each recipe must have complete, cookable ingredients and directions. Nutrition values must be estimated per serving. Include 6-8 relevant tags per recipe covering cuisine, dietary labels, meal type, and characteristics."""

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
                        max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    response_text = message.content[0].text
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
async def save_menu_recipes(request: Request, courses: list = []):
    """Save all recipes from a generated menu, fully enriched with AI data and photos."""
    user = await get_current_user(request)
    body = await request.json()
    courses = body.get("courses", [])
    menu_title = body.get("menu_title", "Menu")
    saved_ids = []

    # Find photos for all recipes in parallel
    from app.services.photo_finder import find_recipe_photo

    conn = await get_conn()
    try:
        for course in courses:
            recipe = course.get("recipe", {})
            if not recipe.get("title"):
                continue
            rid = f"rcp-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            # Get nutrition from the generated recipe (already included in prompt)
            nutrition = recipe.get("nutrition", {})

            # Find a photo for this recipe
            photo_url = await find_recipe_photo(recipe["title"])
            photo_urls = [photo_url] if photo_url else []

            # Build rich notes with menu context
            notes_parts = [f"Part of menu: {menu_title}"]
            if course.get("course_name"):
                notes_parts.append(f"Course: {course['course_name']}")
            if course.get("wine_pairing"):
                notes_parts.append(f"Wine pairing: {course['wine_pairing']}")
            if course.get("plating_tip"):
                notes_parts.append(f"Plating: {course['plating_tip']}")
            notes = "\n".join(notes_parts)

            # If nutrition is missing, run AI enrichment
            if not nutrition:
                from app.services.enrichment import enrich_recipe
                enriched = await enrich_recipe(recipe, force_tags=True)
                if enriched:
                    nutrition = enriched.get("nutrition", {})
                    # Merge any extra tags from enrichment
                    extra_tags = enriched.get("suggested_tags", [])
                    existing_tags = recipe.get("suggested_tags", [])
                    recipe["suggested_tags"] = list(set(existing_tags + extra_tags))
                    # Fill description if missing
                    if enriched.get("description") and not recipe.get("description"):
                        recipe["description"] = enriched["description"]

            await conn.execute(
                """INSERT INTO recipes (id, user_id, title, description, ingredients, directions, servings,
                   prep_time_minutes, cook_time_minutes, total_time_minutes, notes, nutrition, photo_urls,
                   rating, is_favourite, is_pinned, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, user["id"], recipe["title"], recipe.get("description", ""),
                 json.dumps(recipe.get("ingredients", [])), json.dumps(recipe.get("directions", [])),
                 recipe.get("servings"), recipe.get("prep_time_minutes"), recipe.get("cook_time_minutes"),
                 recipe.get("total_time_minutes"), notes,
                 json.dumps(nutrition), json.dumps(photo_urls),
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

            saved_ids.append({
                "id": rid,
                "title": recipe["title"],
                "course": course.get("course_name", ""),
                "photo": photo_urls[0] if photo_urls else None,
                "tags": tags_added,
                "has_nutrition": bool(nutrition),
            })

        # Link all menu recipes together
        for i, item in enumerate(saved_ids):
            for j, other in enumerate(saved_ids):
                if i != j:
                    await conn.execute("INSERT OR IGNORE INTO recipe_links (recipe_id, linked_recipe_id, link_type) VALUES (?,?,?)",
                                       (item["id"], other["id"], "menu"))

        await conn.commit()
        await log_activity(user["id"], "menu_save", {"menu": menu_title, "recipes": len(saved_ids)})
        return {"status": "saved", "recipes": saved_ids}
    finally:
        await conn.close()


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
