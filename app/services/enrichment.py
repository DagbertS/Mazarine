import json
import os
import re
from typing import Optional
from app.config import get_ai_config

async def enrich_recipe(recipe: dict, force_tags: bool = False) -> dict:
    ai_config = get_ai_config()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {}

    missing_fields = []
    if not recipe.get("description"):
        missing_fields.append("description")
    if not recipe.get("nutrition") or recipe.get("nutrition") in ("{}", {}, "{}"):
        missing_fields.append("nutrition")
    if not recipe.get("prep_time_minutes"):
        missing_fields.append("prep_time_minutes")
    if not recipe.get("cook_time_minutes"):
        missing_fields.append("cook_time_minutes")
    if not recipe.get("total_time_minutes"):
        missing_fields.append("total_time_minutes")

    # Always include suggested_tags when force_tags is True
    always_suggest_tags = force_tags or ai_config.get("auto_enrich", False)

    if not missing_fields and not always_suggest_tags:
        return {}

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        existing_tags = []
        if recipe.get("tags"):
            existing_tags = [t.get("name", t) if isinstance(t, dict) else t for t in recipe["tags"]]

        fields_instruction = ""
        if missing_fields:
            fields_instruction = f"""Missing fields to fill: {', '.join(missing_fields)}

Return JSON with these keys (include only the missing ones):
- "description": a 1-2 sentence appetising description
- "nutrition": object with calories (number), protein (grams), carbs (grams), fat (grams), fiber (grams) - estimated per serving
- "prep_time_minutes": integer
- "cook_time_minutes": integer
- "total_time_minutes": integer
"""
        else:
            fields_instruction = "All standard fields are filled. Only return suggested_tags.\n"

        prompt = f"""Given this recipe, enrich it with missing data and tags. Return ONLY valid JSON.

Recipe title: {recipe.get('title', '')}
Description: {recipe.get('description', '')}
Ingredients: {json.dumps(recipe.get('ingredients', []))}
Directions: {json.dumps(recipe.get('directions', []))}
Servings: {recipe.get('servings', 'unknown')}
Existing tags: {json.dumps(existing_tags)}

{fields_instruction}
ALWAYS include this key:
- "suggested_tags": array of 4-8 relevant tags. Include cuisine type (e.g. "French", "Japanese", "Indian", "Thai", "Mexican", "Italian", "Middle Eastern"), dietary labels (e.g. "Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Healthy"), meal type (e.g. "Soup", "Salad", "Main Course", "Side Dish", "Appetizer", "Comfort Food"), and characteristics (e.g. "Quick", "One-Pot", "High-Protein", "Low-Calorie", "Weeknight"). Do NOT repeat tags that already exist: {json.dumps(existing_tags)}

Be accurate with nutrition estimates. Return ONLY valid JSON, no markdown."""

        model = ai_config.get("model", "claude-sonnet-4-20250514")
        message = await client.messages.create(
            model=model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        json_text = response_text
        if "```" in response_text:
            m = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL)
            if m:
                json_text = m.group(1)

        enriched = json.loads(json_text.strip())
        return enriched

    except Exception as e:
        print(f"Enrichment error: {e}")
        return {}
