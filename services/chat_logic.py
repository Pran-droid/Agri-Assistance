from typing import Any, Dict

import models
from .gemini import generate_gemini_response
from .market import get_market_prices
from .pdf_context import get_context_from_pdfs
from .weather import get_weather


def handle_intents(user: Dict[str, Any], english_message: str) -> str:
    lowered = english_message.lower()

    if "weather" in lowered:
        return get_weather(user.get("location", ""))
    if "market" in lowered or "price" in lowered:
        return get_market_prices(user.get("location", ""))
    if lowered.startswith("update my location to"):
        new_location = english_message[len("update my location to"):].strip()
        if new_location:
            models.update_user_location(user["_id"], new_location)
            return f"Your location has been updated to {new_location}."
        return "I could not detect the new location. Please try again."
    if lowered.startswith("update my crops to"):
        crops_text = english_message[len("update my crops to"):].strip()
        if crops_text:
            crops_list = [item.strip() for item in crops_text.split(",") if item.strip()]
            models.update_user_crops(user["_id"], crops_list)
            readable = ", ".join(crops_list) if crops_list else "none"
            return f"Your crops have been updated to {readable}."
        return "I could not detect the new crops list. Please try again."

    pdf_context = get_context_from_pdfs(english_message)
    return generate_gemini_response(english_message, pdf_context)
