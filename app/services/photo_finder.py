import httpx
import re
from typing import Optional

async def find_recipe_photo(recipe_title: str) -> Optional[str]:
    """Find a representative food photo for a recipe using Unsplash source (no API key needed)."""
    # Clean the title for search
    clean = re.sub(r'[^\w\s]', '', recipe_title).strip()
    # Use Unsplash Source which returns a direct image URL (no API key required)
    # This gives a random relevant food photo
    search_terms = f"{clean} food dish"
    url = f"https://source.unsplash.com/800x600/?{search_terms.replace(' ', ',')}"

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.head(url)
            # Unsplash redirects to the actual image URL
            final_url = str(resp.url)
            if "images.unsplash.com" in final_url:
                return final_url
            return url
    except Exception:
        return None


async def find_recipe_photos_batch(titles: list) -> dict:
    """Find photos for multiple recipes. Returns {title: photo_url}."""
    results = {}
    for title in titles:
        photo = await find_recipe_photo(title)
        if photo:
            results[title] = photo
    return results
