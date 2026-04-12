import re
from typing import Optional
from app.services.scaler import parse_quantity

AISLE_MAP = {
    "Produce": [
        "apple", "avocado", "banana", "basil", "bean sprout", "bell pepper", "berry", "blueberry",
        "broccoli", "cabbage", "carrot", "cauliflower", "celery", "cherry", "cilantro", "corn",
        "cucumber", "dill", "eggplant", "garlic", "ginger", "grape", "green bean", "green onion",
        "herb", "jalape", "kale", "leek", "lemon", "lettuce", "lime", "mango", "melon",
        "mint", "mushroom", "onion", "orange", "parsley", "peach", "pear", "pepper", "pineapple",
        "potato", "pumpkin", "radish", "raspberry", "rosemary", "sage", "scallion", "shallot",
        "spinach", "squash", "strawberry", "sweet potato", "thyme", "tomato", "zucchini",
    ],
    "Dairy & Eggs": [
        "butter", "cheese", "cream", "cream cheese", "egg", "half and half", "milk",
        "mozzarella", "parmesan", "ricotta", "sour cream", "whipped cream", "yogurt",
    ],
    "Meat & Seafood": [
        "bacon", "beef", "chicken", "chorizo", "clam", "cod", "crab", "duck", "fish",
        "ground beef", "ground turkey", "ham", "lamb", "lobster", "mussels", "pork",
        "prosciutto", "salmon", "sausage", "shrimp", "steak", "tilapia", "tuna", "turkey", "veal",
    ],
    "Bakery": [
        "bagel", "baguette", "bread", "brioche", "bun", "ciabatta", "croissant",
        "english muffin", "flatbread", "naan", "pita", "roll", "sourdough", "tortilla", "wrap",
    ],
    "Frozen": [
        "frozen", "ice cream", "sorbet", "frozen vegetable", "frozen fruit",
    ],
    "Canned Goods": [
        "canned", "can of", "tomato paste", "tomato sauce", "diced tomato",
        "coconut milk", "chickpea", "black bean", "kidney bean", "lentil",
    ],
    "Pasta & Grains": [
        "barley", "basmati", "bread crumb", "bulgur", "couscous", "farro",
        "fettuccine", "flour tortilla", "fusilli", "jasmine rice", "linguine",
        "macaroni", "noodle", "oat", "orzo", "pasta", "penne", "polenta",
        "quinoa", "rice", "rigatoni", "spaghetti", "udon",
    ],
    "Condiments & Sauces": [
        "bbq sauce", "hot sauce", "ketchup", "mayonnaise", "mustard", "salsa",
        "soy sauce", "sriracha", "teriyaki", "vinaigrette", "worcestershire",
    ],
    "Spices & Seasonings": [
        "allspice", "bay leaf", "black pepper", "cardamom", "cayenne", "chili flake",
        "chili powder", "cinnamon", "clove", "coriander", "cumin", "curry",
        "garlic powder", "ginger powder", "nutmeg", "onion powder", "oregano",
        "paprika", "pepper", "red pepper", "salt", "seasoning", "spice", "turmeric", "vanilla",
    ],
    "Baking": [
        "baking powder", "baking soda", "brown sugar", "chocolate chip", "cocoa",
        "confectioner", "cornstarch", "extract", "flour", "food coloring",
        "gelatin", "honey", "icing", "maple syrup", "molasses", "powdered sugar",
        "sugar", "yeast",
    ],
    "Oils & Vinegars": [
        "apple cider vinegar", "balsamic", "canola oil", "coconut oil",
        "cooking spray", "olive oil", "rice vinegar", "sesame oil",
        "vegetable oil", "vinegar", "wine vinegar",
    ],
    "Beverages": [
        "beer", "broth", "club soda", "coffee", "juice", "stock", "tea", "water", "wine",
    ],
    "Snacks": [
        "chip", "cracker", "granola", "nut", "almond", "cashew", "peanut",
        "pecan", "pistachio", "walnut", "popcorn", "pretzel", "seed",
    ],
}

def assign_aisle(ingredient_name: str) -> str:
    name_lower = ingredient_name.lower().strip()
    for aisle, keywords in AISLE_MAP.items():
        for kw in keywords:
            if kw in name_lower:
                return aisle
    return "Other"

def _normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\s*\(.*?\)\s*", " ", name)
    name = re.sub(r",.*$", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if name.endswith("es") and len(name) > 4:
        base = name[:-2]
    elif name.endswith("s") and not name.endswith("ss") and len(name) > 3:
        base = name[:-1]
    else:
        base = name
    return base

def _units_compatible(u1: str, u2: str) -> bool:
    if not u1 or not u2:
        return u1 == u2
    return u1.lower().strip() == u2.lower().strip()

def consolidate_ingredients(new_ingredients: list, existing_items: list) -> list:
    result = []
    existing_map = {}
    for item in existing_items:
        key = _normalize_name(item.get("name", ""))
        existing_map[key] = item

    for ing in new_ingredients:
        name = ing.get("name", "")
        key = _normalize_name(name)
        qty = parse_quantity(str(ing.get("qty", "")))
        unit = ing.get("unit", "")

        if key in existing_map:
            ex = existing_map[key]
            ex_qty = ex.get("quantity") or 0
            if _units_compatible(unit, ex.get("unit", "")):
                new_qty = (ex_qty or 0) + (qty or 0) if qty else ex_qty
                result.append({
                    "name": ex.get("name", name),
                    "quantity": new_qty,
                    "unit": ex.get("unit") or unit,
                    "_existing_id": ex.get("id"),
                })
            else:
                result.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                })
        else:
            result.append({
                "name": name,
                "quantity": qty,
                "unit": unit,
            })
            existing_map[key] = {"name": name, "quantity": qty, "unit": unit}

    return result
