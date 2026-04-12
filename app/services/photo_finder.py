import httpx
import re
import hashlib
from typing import Optional


# Map recipe keywords to Foodish API categories (all available categories)
FOODISH_CATEGORIES = {
    "burger": "burger", "hamburger": "burger",
    "pizza": "pizza", "flatbread": "pizza",
    "pasta": "pasta", "spaghetti": "pasta", "penne": "pasta", "linguine": "pasta",
    "fettuccine": "pasta", "macaroni": "pasta", "noodle": "pasta", "lasagna": "pasta",
    "rice": "rice", "risotto": "rice", "paella": "rice", "biryani": "biryani",
    "biriyani": "biryani", "fried rice": "rice", "bibimbap": "rice",
    "dessert": "dessert", "cake": "dessert", "brownie": "dessert", "cookie": "dessert",
    "pie": "dessert", "tart": "dessert", "pudding": "dessert", "ice cream": "dessert",
    "bread": "dessert", "scone": "dessert", "muffin": "dessert",
    "dosa": "dosa", "idly": "idly", "idli": "idly",
    "samosa": "samosa",
}

# Map broader recipe types to TheMealDB categories for fallback
MEAL_KEYWORDS = {
    "soup": "soup", "chowder": "soup", "broth": "soup", "stew": "soup",
    "salad": "salad", "slaw": "salad",
    "curry": "curry", "masala": "curry",
    "chicken": "chicken", "poultry": "chicken",
    "beef": "beef", "steak": "beef",
    "fish": "seafood", "salmon": "seafood", "shrimp": "seafood", "tuna": "seafood",
    "pork": "pork", "bacon": "pork",
    "vegetable": "vegetable", "vegan": "vegetable", "vegetarian": "vegetable",
    "egg": "breakfast", "omelette": "breakfast", "pancake": "breakfast",
    "french toast": "breakfast", "waffle": "breakfast",
}


async def find_recipe_photo(recipe_title: str) -> Optional[str]:
    """Find a food photo for a recipe. Uses multiple free sources."""
    title_lower = recipe_title.lower().strip()

    # Method 1: Foodish API — category-matched food photos
    photo = await _try_foodish(title_lower)
    if photo:
        return photo

    # Method 2: TheMealDB search — real dish photos
    photo = await _try_mealdb(recipe_title)
    if photo:
        return photo

    # Method 3: Fallback — generic food from Foodish
    photo = await _try_foodish_random()
    if photo:
        return photo

    return None


async def _try_foodish(title_lower: str) -> Optional[str]:
    """Match recipe to a Foodish category and get a relevant food image."""
    matched_category = None
    for keyword, category in FOODISH_CATEGORIES.items():
        if keyword in title_lower:
            matched_category = category
            break

    if not matched_category:
        return None

    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(f"https://foodish-api.com/api/images/{matched_category}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("image")
    except Exception:
        pass
    return None


async def _try_mealdb(title: str) -> Optional[str]:
    """Search TheMealDB for a matching dish photo. Free API, no key needed."""
    try:
        # Search by meal name
        clean = re.sub(r'[^\w\s]', '', title).strip()
        # Try first word or two for broader matches
        search_terms = clean.split()[:3]

        async with httpx.AsyncClient(timeout=6) as client:
            for term in search_terms:
                if len(term) < 3:
                    continue
                resp = await client.get(
                    f"https://www.themealdb.com/api/json/v1/1/search.php",
                    params={"s": term},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    meals = data.get("meals")
                    if meals:
                        return meals[0].get("strMealThumb")
    except Exception:
        pass
    return None


async def _try_foodish_random() -> Optional[str]:
    """Get a random food image from Foodish as ultimate fallback."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("https://foodish-api.com/api/")
            if resp.status_code == 200:
                return resp.json().get("image")
    except Exception:
        pass
    return None
