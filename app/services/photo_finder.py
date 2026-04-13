import httpx
import re
import os
from typing import Optional


async def find_recipe_photo(recipe_title: str) -> Optional[str]:
    """Find a high-quality food photo for a recipe. Tries Pexels first, then TheMealDB."""

    # Method 1: Pexels — high quality, stylish food photography
    photo = await _try_pexels(recipe_title)
    if photo:
        return photo

    # Method 2: TheMealDB — real dish photos from meal database
    photo = await _try_mealdb(recipe_title)
    if photo:
        return photo

    return None


async def _try_pexels(title: str) -> Optional[str]:
    """Search Pexels for a food photo. Returns a high-quality landscape image URL."""
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        return None

    # Build a focused food search query from the recipe title
    query = _build_search_query(title)

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                "https://api.pexels.com/v1/search",
                params={
                    "query": query,
                    "per_page": 5,
                    "orientation": "landscape",
                    "size": "medium",
                },
                headers={"Authorization": api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                photos = data.get("photos", [])
                if photos:
                    # Pick the best photo — prefer wider aspect ratios (food photography style)
                    best = photos[0]
                    return best["src"]["large"]

            # If first query didn't work, try a simpler one
            if not photos:
                simple_query = _simplify_query(title)
                resp2 = await client.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": simple_query, "per_page": 3, "orientation": "landscape"},
                    headers={"Authorization": api_key},
                )
                if resp2.status_code == 200:
                    photos2 = resp2.json().get("photos", [])
                    if photos2:
                        return photos2[0]["src"]["large"]

    except Exception as e:
        print(f"[PHOTO] Pexels error: {e}")
    return None


async def _try_mealdb(title: str) -> Optional[str]:
    """Search TheMealDB for a matching dish photo."""
    try:
        clean = re.sub(r'[^\w\s]', '', title).strip()
        search_terms = clean.split()[:2]  # First 2 words

        async with httpx.AsyncClient(timeout=6) as client:
            for term in search_terms:
                if len(term) < 3:
                    continue
                resp = await client.get(
                    "https://www.themealdb.com/api/json/v1/1/search.php",
                    params={"s": term},
                )
                if resp.status_code == 200:
                    meals = resp.json().get("meals")
                    if meals:
                        return meals[0].get("strMealThumb")
    except Exception:
        pass
    return None


def _build_search_query(title: str) -> str:
    """Build an effective Pexels search query from a recipe title."""
    t = title.lower().strip()

    # Remove common prefixes that don't help image search
    for prefix in ["best ", "easy ", "simple ", "quick ", "classic ", "homemade ",
                    "the ", "my ", "our ", "perfect "]:
        if t.startswith(prefix):
            t = t[len(prefix):]

    # Add "food dish" to help Pexels find food photos specifically
    return f"{t} food dish plated"


def _simplify_query(title: str) -> str:
    """Create a simpler search query by extracting the key food noun."""
    t = title.lower().strip()

    # Extract the main dish/food word
    food_words = []
    for word in t.split():
        # Skip generic cooking words
        if word in ("with", "and", "the", "in", "on", "a", "an", "of", "for",
                     "easy", "best", "quick", "simple", "classic", "homemade",
                     "baked", "roasted", "grilled", "pan", "fried", "seared",
                     "fresh", "warm", "cold", "hot", "recipe", "style"):
            continue
        food_words.append(word)

    if food_words:
        # Use up to 3 key words + "food"
        return " ".join(food_words[:3]) + " food"
    return title + " food"
