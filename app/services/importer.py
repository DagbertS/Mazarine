import httpx
import json
import re
from typing import Optional

async def import_from_url(url: str) -> dict:
    try:
        from recipe_scrapers import scrape_html
    except ImportError:
        scrape_html = None

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        html = resp.text

    if scrape_html:
        try:
            scraper = scrape_html(html=html, org_url=url)
            ingredients = []
            for ing in scraper.ingredients():
                parsed = _parse_ingredient_line(ing)
                ingredients.append(parsed)

            directions = []
            raw_instructions = scraper.instructions()
            if raw_instructions:
                steps = raw_instructions.split("\n")
                for i, step in enumerate(steps):
                    step = step.strip()
                    if step:
                        step = re.sub(r"^\d+[\.\)]\s*", "", step)
                        timer = _extract_timer(step)
                        directions.append({"step": i + 1, "text": step, "timer_minutes": timer})

            photo = None
            try:
                photo = scraper.image()
            except Exception:
                pass

            nutrition = {}
            try:
                nutr = scraper.nutrients()
                if nutr:
                    nutrition = nutr
            except Exception:
                pass

            servings = None
            try:
                servings = int(scraper.yields().split()[0])
            except Exception:
                pass

            prep_time = None
            cook_time = None
            total_time = None
            try:
                prep_time = scraper.prep_time()
            except Exception:
                pass
            try:
                cook_time = scraper.cook_time()
            except Exception:
                pass
            try:
                total_time = scraper.total_time()
            except Exception:
                pass

            return {
                "title": scraper.title() or "Imported Recipe",
                "description": _safe_call(scraper, "description", ""),
                "ingredients": ingredients,
                "directions": directions,
                "servings": servings,
                "prep_time_minutes": prep_time,
                "cook_time_minutes": cook_time,
                "total_time_minutes": total_time,
                "source_url": url,
                "source_name": _extract_domain(url),
                "nutrition": nutrition,
                "photo_urls": [photo] if photo else [],
            }
        except Exception:
            pass

    return _fallback_parse(html, url)

def _safe_call(obj, method, default=""):
    try:
        return getattr(obj, method)()
    except Exception:
        return default

def _fallback_parse(html: str, url: str) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "")
    if not title:
        t = soup.find("title")
        title = t.text.strip() if t else "Imported Recipe"

    description = ""
    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        description = og_desc.get("content", "")

    photo = ""
    og_img = soup.find("meta", property="og:image")
    if og_img:
        photo = og_img.get("content", "")

    ld_json = soup.find("script", type="application/ld+json")
    if ld_json:
        try:
            data = json.loads(ld_json.string)
            if isinstance(data, list):
                data = data[0]
            if data.get("@type") == "Recipe" or (isinstance(data.get("@graph"), list)):
                if isinstance(data.get("@graph"), list):
                    for item in data["@graph"]:
                        if item.get("@type") == "Recipe":
                            data = item
                            break
                return _parse_ld_json(data, url)
        except Exception:
            pass

    return {
        "title": title,
        "description": description,
        "ingredients": [],
        "directions": [],
        "servings": None,
        "prep_time_minutes": None,
        "cook_time_minutes": None,
        "total_time_minutes": None,
        "source_url": url,
        "source_name": _extract_domain(url),
        "nutrition": {},
        "photo_urls": [photo] if photo else [],
    }

def _parse_ld_json(data: dict, url: str) -> dict:
    ingredients = []
    for ing in data.get("recipeIngredient", []):
        ingredients.append(_parse_ingredient_line(str(ing)))

    directions = []
    instructions = data.get("recipeInstructions", [])
    for i, step in enumerate(instructions):
        text = step.get("text", step) if isinstance(step, dict) else str(step)
        timer = _extract_timer(text)
        directions.append({"step": i + 1, "text": text, "timer_minutes": timer})

    servings = None
    y = data.get("recipeYield")
    if y:
        if isinstance(y, list):
            y = y[0]
        m = re.search(r"\d+", str(y))
        if m:
            servings = int(m.group())

    photo = data.get("image")
    if isinstance(photo, list):
        photo = photo[0] if photo else None
    if isinstance(photo, dict):
        photo = photo.get("url")

    return {
        "title": data.get("name", "Imported Recipe"),
        "description": data.get("description", ""),
        "ingredients": ingredients,
        "directions": directions,
        "servings": servings,
        "prep_time_minutes": _parse_iso_duration(data.get("prepTime")),
        "cook_time_minutes": _parse_iso_duration(data.get("cookTime")),
        "total_time_minutes": _parse_iso_duration(data.get("totalTime")),
        "source_url": url,
        "source_name": _extract_domain(url),
        "nutrition": _parse_nutrition(data.get("nutrition", {})),
        "photo_urls": [photo] if photo else [],
    }

def _parse_ingredient_line(line: str) -> dict:
    line = line.strip()
    match = re.match(r"^([\d\s/½¼¾⅓⅔⅛\.,-]+)\s*(cups?|tbsp|tsp|tablespoons?|teaspoons?|oz|ounces?|lbs?|pounds?|g|grams?|kg|ml|l|liters?|litres?|cloves?|pinch|dash|bunch|handful|pieces?|slices?|cans?|sticks?)?\s*(.+)", line, re.IGNORECASE)
    if match:
        qty_str = match.group(1).strip()
        unit = (match.group(2) or "").strip()
        rest = match.group(3).strip()
        note_match = re.match(r"^(.+?),\s*(.+)$", rest)
        name = note_match.group(1) if note_match else rest
        note = note_match.group(2) if note_match else ""
        return {"qty": qty_str, "unit": unit, "name": name, "note": note, "group": ""}
    return {"qty": "", "unit": "", "name": line, "note": "", "group": ""}

def _extract_timer(text: str) -> Optional[int]:
    patterns = [
        r"(\d+)\s*(?:to\s*\d+\s*)?minutes?",
        r"(\d+)\s*(?:to\s*\d+\s*)?mins?",
        r"(\d+)\s*hours?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if "hour" in pat:
                val *= 60
            return val
    return None

def _parse_iso_duration(dur: Optional[str]) -> Optional[int]:
    if not dur:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(dur))
    if m:
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        return hours * 60 + minutes
    return None

def _parse_nutrition(data: dict) -> dict:
    if not data:
        return {}
    result = {}
    for key in ("calories", "fatContent", "proteinContent", "carbohydrateContent", "fiberContent",
                "sugarContent", "sodiumContent", "cholesterolContent"):
        val = data.get(key)
        if val:
            num = re.search(r"[\d.]+", str(val))
            if num:
                clean_key = key.replace("Content", "")
                result[clean_key] = float(num.group())
    return result

def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    return domain
