import re
from fractions import Fraction
from typing import Optional

METRIC_TO_IMPERIAL = {
    "g": ("oz", 0.03527396),
    "kg": ("lbs", 2.20462),
    "ml": ("fl oz", 0.033814),
    "l": ("cups", 4.22675),
    "cm": ("inches", 0.393701),
}

IMPERIAL_TO_METRIC = {
    "oz": ("g", 28.3495),
    "ounce": ("g", 28.3495),
    "ounces": ("g", 28.3495),
    "lb": ("kg", 0.453592),
    "lbs": ("kg", 0.453592),
    "pound": ("kg", 0.453592),
    "pounds": ("kg", 0.453592),
    "cup": ("ml", 236.588),
    "cups": ("ml", 236.588),
    "tbsp": ("ml", 14.7868),
    "tablespoon": ("ml", 14.7868),
    "tablespoons": ("ml", 14.7868),
    "tsp": ("ml", 4.92892),
    "teaspoon": ("ml", 4.92892),
    "teaspoons": ("ml", 4.92892),
    "fl oz": ("ml", 29.5735),
    "quart": ("l", 0.946353),
    "quarts": ("l", 0.946353),
    "gallon": ("l", 3.78541),
    "gallons": ("l", 3.78541),
    "pint": ("ml", 473.176),
    "pints": ("ml", 473.176),
    "inch": ("cm", 2.54),
    "inches": ("cm", 2.54),
}

UNICODE_FRACTIONS = {
    "½": 0.5, "⅓": 1/3, "⅔": 2/3,
    "¼": 0.25, "¾": 0.75,
    "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
    "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
    "⅙": 1/6, "⅚": 5/6,
}

def parse_quantity(qty_str: str) -> Optional[float]:
    if not qty_str or not qty_str.strip():
        return None
    s = qty_str.strip()
    for uf, val in UNICODE_FRACTIONS.items():
        if uf in s:
            rest = s.replace(uf, "").strip()
            whole = float(rest) if rest else 0
            return whole + val

    range_match = re.match(r"([\d./]+)\s*[-–to]+\s*([\d./]+)", s)
    if range_match:
        low = _parse_frac(range_match.group(1))
        high = _parse_frac(range_match.group(2))
        if low is not None and high is not None:
            return (low + high) / 2

    parts = s.split()
    if len(parts) == 2:
        whole = _parse_frac(parts[0])
        frac = _parse_frac(parts[1])
        if whole is not None and frac is not None:
            return whole + frac

    return _parse_frac(s)

def _parse_frac(s: str) -> Optional[float]:
    try:
        if "/" in s:
            return float(Fraction(s))
        return float(s)
    except (ValueError, ZeroDivisionError):
        return None

def format_quantity(val: float) -> str:
    if val == int(val):
        return str(int(val))
    common = {0.25: "1/4", 0.5: "1/2", 0.75: "3/4",
              0.33: "1/3", 0.67: "2/3", 0.125: "1/8"}
    frac_part = val - int(val)
    for threshold, label in common.items():
        if abs(frac_part - threshold) < 0.03:
            whole = int(val)
            return f"{whole} {label}" if whole else label
    return f"{val:.2f}".rstrip("0").rstrip(".")

def scale_ingredients(ingredients: list, original_servings: int, new_servings: int) -> list:
    if not original_servings or original_servings == new_servings:
        return ingredients
    ratio = new_servings / original_servings
    scaled = []
    for ing in ingredients:
        new_ing = dict(ing)
        qty = parse_quantity(str(ing.get("qty", "")))
        if qty is not None:
            new_qty = qty * ratio
            new_ing["qty"] = format_quantity(new_qty)
            new_ing["qty_float"] = round(new_qty, 3)
        scaled.append(new_ing)
    return scaled

def convert_unit(value: float, from_unit: str, to_system: str = "metric") -> dict:
    from_lower = from_unit.lower().strip()
    if to_system == "metric" and from_lower in IMPERIAL_TO_METRIC:
        target_unit, factor = IMPERIAL_TO_METRIC[from_lower]
        return {"value": round(value * factor, 2), "unit": target_unit}
    elif to_system == "imperial" and from_lower in METRIC_TO_IMPERIAL:
        target_unit, factor = METRIC_TO_IMPERIAL[from_lower]
        return {"value": round(value * factor, 2), "unit": target_unit}
    return {"value": value, "unit": from_unit}

def convert_recipe_units(ingredients: list, to_system: str = "metric") -> list:
    converted = []
    for ing in ingredients:
        new_ing = dict(ing)
        qty = parse_quantity(str(ing.get("qty", "")))
        unit = ing.get("unit", "")
        if qty is not None and unit:
            result = convert_unit(qty, unit, to_system)
            new_ing["qty"] = format_quantity(result["value"])
            new_ing["qty_float"] = result["value"]
            new_ing["unit"] = result["unit"]
        converted.append(new_ing)
    return converted
