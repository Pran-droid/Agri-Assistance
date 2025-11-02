from typing import Any, Dict, Generator
import time

import models
from .gemini import generate_gemini_response, generate_gemini_response_stream
from .market import get_market_prices, search_commodity_prices
from .pdf_context import get_context_from_pdfs
from .weather import get_weather


def handle_intents(user: Dict[str, Any], english_message: str) -> str:
    lowered = english_message.lower()

    if "weather" in lowered:
        return get_weather(user.get("location", ""))
    if "market" in lowered or "price" in lowered:
        # Get farmer's crops and location from profile
        user_crops = user.get("crops", [])
        user_location = user.get("location", "")
        
        # If farmer has crops in profile, show prices for their crops
        if user_crops:
            response_parts = []
            for crop in user_crops[:3]:  # Limit to first 3 crops to avoid too long response
                crop_prices = search_commodity_prices(crop, user_location)
                response_parts.append(crop_prices)
            return "\n\n---\n\n".join(response_parts)
        else:
            # Fallback to general market prices for their location
            return get_market_prices(user_location)
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


def handle_intents_stream(user: Dict[str, Any], english_message: str) -> Generator[str, None, None]:
    """Stream-enabled version of handle_intents for real-time responses."""
    lowered = english_message.lower()

    # Quick responses (non-streaming)
    if "weather" in lowered:
        yield get_weather(user.get("location", ""))
        return
    if "market" in lowered or "price" in lowered:
        # Get farmer's crops and location from profile
        user_crops = user.get("crops", [])
        user_location = user.get("location", "")
        
        # If farmer has crops in profile, show prices for their crops
        if user_crops:
            for crop in user_crops[:3]:  # Limit to first 3 crops
                crop_prices = search_commodity_prices(crop, user_location)
                yield crop_prices
                if len(user_crops) > 1:
                    yield "\n\n---\n\n"
        else:
            # Fallback to general market prices for their location
            yield get_market_prices(user_location)
        return
    if lowered.startswith("update my location to"):
        new_location = english_message[len("update my location to"):].strip()
        if new_location:
            models.update_user_location(user["_id"], new_location)
            yield f"Your location has been updated to {new_location}."
        else:
            yield "I could not detect the new location. Please try again."
        return
    if lowered.startswith("update my crops to"):
        crops_text = english_message[len("update my crops to"):].strip()
        if crops_text:
            crops_list = [item.strip() for item in crops_text.split(",") if item.strip()]
            models.update_user_crops(user["_id"], crops_list)
            readable = ", ".join(crops_list) if crops_list else "none"
            yield f"Your crops have been updated to {readable}."
        else:
            yield "I could not detect the new crops list. Please try again."
        return

    # Stream Gemini response
    start_time = time.time()
    pdf_context = get_context_from_pdfs(english_message)
    pdf_time = time.time()
    print(f"⏱️  PDF context retrieval took: {pdf_time - start_time:.4f} seconds")
    
    for chunk in generate_gemini_response_stream(english_message, pdf_context):
        yield chunk
