import json
import re
from typing import Optional


def normalize_title(title: str) -> str:
    """Normalize a title for comparison."""
    t = title.lower().strip()
    # Remove common prefixes
    for prefix in ["best ", "easy ", "simple ", "quick ", "classic ", "homemade ", "the ", "my ", "our "]:
        if t.startswith(prefix):
            t = t[len(prefix):]
    # Remove special chars
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def title_similarity(a: str, b: str) -> float:
    """Calculate similarity between two titles (0.0 to 1.0)."""
    na = normalize_title(a)
    nb = normalize_title(b)

    # Exact match after normalization
    if na == nb:
        return 1.0

    # One contains the other
    if na in nb or nb in na:
        return 0.85

    # Word overlap (Jaccard)
    words_a = set(na.split())
    words_b = set(nb.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    jaccard = len(intersection) / len(union)

    return jaccard


def ingredient_overlap(ingredients_a: list, ingredients_b: list) -> float:
    """Calculate ingredient overlap between two recipes (0.0 to 1.0)."""
    def extract_names(ingredients):
        names = set()
        for ing in ingredients:
            name = ing.get("name", "") if isinstance(ing, dict) else str(ing)
            name = re.sub(r'[^\w\s]', '', name.lower()).strip()
            # Remove common modifiers
            for mod in ["fresh ", "dried ", "ground ", "chopped ", "minced ", "sliced ", "diced "]:
                name = name.replace(mod, "")
            name = name.strip()
            if name and len(name) > 1:
                names.add(name)
        return names

    names_a = extract_names(ingredients_a)
    names_b = extract_names(ingredients_b)

    if not names_a or not names_b:
        return 0.0

    # Fuzzy match: count how many ingredients from A appear in B
    matched = 0
    for na in names_a:
        for nb in names_b:
            if na in nb or nb in na:
                matched += 1
                break

    # Normalize by the smaller recipe
    smaller = min(len(names_a), len(names_b))
    return matched / smaller if smaller > 0 else 0.0


def is_potential_duplicate(new_recipe: dict, existing_recipe: dict, threshold: float = 0.5) -> Optional[dict]:
    """
    Check if a new recipe is a potential duplicate of an existing one.
    Returns a match dict with score and details if it's a potential duplicate, None otherwise.
    """
    new_title = new_recipe.get("title", "")
    existing_title = existing_recipe.get("title", "")

    t_sim = title_similarity(new_title, existing_title)

    # Parse ingredients
    new_ings = new_recipe.get("ingredients", [])
    if isinstance(new_ings, str):
        try:
            new_ings = json.loads(new_ings)
        except (json.JSONDecodeError, TypeError):
            new_ings = []

    ex_ings = existing_recipe.get("ingredients", [])
    if isinstance(ex_ings, str):
        try:
            ex_ings = json.loads(ex_ings)
        except (json.JSONDecodeError, TypeError):
            ex_ings = []

    i_overlap = ingredient_overlap(new_ings, ex_ings)

    # Require minimum title similarity to avoid false positives
    # (e.g. "Mongolian Beef Stir Fry" vs "Easy Stir Fry Sauce" share words but are different dishes)
    if t_sim < 0.4:
        return None

    # Combined score: title similarity weighted more heavily
    score = (t_sim * 0.65) + (i_overlap * 0.35)

    if score >= threshold:
        return {
            "score": round(score, 3),
            "title_similarity": round(t_sim, 3),
            "ingredient_overlap": round(i_overlap, 3),
            "existing_id": existing_recipe.get("id"),
            "existing_title": existing_title,
        }

    return None


async def find_duplicates(new_recipe: dict, user_id: str, threshold: float = 0.5) -> list:
    """
    Find potential duplicates for a new recipe in the user's collection.
    Returns a list of match dicts sorted by score descending.
    """
    from app.database import get_conn, _row_dict

    conn = await get_conn()
    try:
        cur = await conn.execute(
            "SELECT id, title, ingredients, description, servings, prep_time_minutes, cook_time_minutes, "
            "total_time_minutes, photo_urls, source_url, source_name, nutrition FROM recipes WHERE user_id = ?",
            (user_id,),
        )
        existing = [_row_dict(r) for r in await cur.fetchall()]
    finally:
        await conn.close()

    matches = []
    for ex in existing:
        match = is_potential_duplicate(new_recipe, ex, threshold=threshold)
        if match:
            # Enrich match with existing recipe summary for the UI
            ex_ings = ex.get("ingredients", "[]")
            if isinstance(ex_ings, str):
                try:
                    ex_ings = json.loads(ex_ings)
                except (json.JSONDecodeError, TypeError):
                    ex_ings = []
            ex_photos = ex.get("photo_urls", "[]")
            if isinstance(ex_photos, str):
                try:
                    ex_photos = json.loads(ex_photos)
                except (json.JSONDecodeError, TypeError):
                    ex_photos = []
            ex_nutrition = ex.get("nutrition", "{}")
            if isinstance(ex_nutrition, str):
                try:
                    ex_nutrition = json.loads(ex_nutrition)
                except (json.JSONDecodeError, TypeError):
                    ex_nutrition = {}

            match["existing_recipe"] = {
                "id": ex["id"],
                "title": ex["title"],
                "description": ex.get("description", ""),
                "ingredients": ex_ings,
                "servings": ex.get("servings"),
                "prep_time_minutes": ex.get("prep_time_minutes"),
                "cook_time_minutes": ex.get("cook_time_minutes"),
                "total_time_minutes": ex.get("total_time_minutes"),
                "photo_urls": ex_photos,
                "source_url": ex.get("source_url", ""),
                "source_name": ex.get("source_name", ""),
                "nutrition": ex_nutrition,
            }
            matches.append(match)

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches
