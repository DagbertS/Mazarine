import json
import os
import re
import base64
from typing import Optional
from app.config import get_ai_config


async def analyze_recipe_image(image_data: bytes, content_type: str = "image/jpeg") -> dict:
    """
    Use Claude's vision to extract a full recipe from an image.
    Handles: cookbook photos, handwritten cards, magazine scans, screenshots, plated food.
    Returns a structured recipe dict.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    ai_config = get_ai_config()
    b64 = base64.standard_b64encode(image_data).decode("utf-8")

    # Map common content types to Claude's expected media types
    media_type = content_type
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        media_type = "image/jpeg"

    prompt = """Analyze this image and extract a complete recipe. The image might be:
- A photo of a cookbook or recipe card
- A handwritten recipe
- A magazine clipping
- A screenshot of a recipe
- A photo of a finished dish (in which case, identify the dish and create the recipe)

Return ONLY valid JSON with this exact structure:
{
  "title": "Recipe name",
  "description": "1-2 sentence appetising description",
  "servings": <number or null>,
  "prep_time_minutes": <number or null>,
  "cook_time_minutes": <number or null>,
  "total_time_minutes": <number or null>,
  "ingredients": [
    {"qty": "amount", "unit": "unit", "name": "ingredient name", "note": "optional note", "group": ""}
  ],
  "directions": [
    {"step": 1, "text": "direction text", "timer_minutes": <number or null>}
  ],
  "nutrition": {"calories": <number>, "protein": <grams>, "carbs": <grams>, "fat": <grams>, "fiber": <grams>},
  "suggested_tags": ["tag1", "tag2", "tag3"],
  "source_type": "ocr",
  "confidence": "high/medium/low"
}

If you can see a recipe with text, extract it faithfully.
If you see a finished dish photo, identify the dish and create a complete recipe for it.
Include 6-8 relevant tags (cuisine, dietary, meal type).
Estimate nutrition per serving.
Extract timer durations from directions where mentioned.
Return ONLY the JSON, no markdown or explanation."""

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        model = ai_config.get("model", "claude-sonnet-4-20250514")

        message = await client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        response_text = message.content[0].text
        json_text = response_text
        if "```" in response_text:
            m = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL)
            if m:
                json_text = m.group(1)

        recipe = json.loads(json_text.strip())
        return recipe

    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse AI response: {str(e)}"}
    except Exception as e:
        return {"error": f"OCR analysis failed: {str(e)}"}
