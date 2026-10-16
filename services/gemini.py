import os
from typing import List, Optional, Generator
from dotenv import load_dotenv

load_dotenv()

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

AVAILABLE_GEMINI_MODELS: List[str] = []
_GEMINI_READY = False
SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Lazy init — configure API key now but DON'T call list_models() at startup
# (that makes a live network request which slows/crashes startup on low-RAM servers)
if GEMINI_API_KEY and genai:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _GEMINI_READY = True
    except Exception:
        _GEMINI_READY = False


def _ensure_models_loaded():
    """Lazily fetch available models on first actual use."""
    global AVAILABLE_GEMINI_MODELS
    if AVAILABLE_GEMINI_MODELS or not _GEMINI_READY:
        return
    try:
        AVAILABLE_GEMINI_MODELS = [
            model.name
            for model in genai.list_models()
            if "generateContent" in getattr(model, "supported_generation_methods", [])
        ]
    except Exception:
        AVAILABLE_GEMINI_MODELS = []


def _build_prompt(user_query: str, pdf_context: str) -> str:
    # Limit PDF context to avoid extremely long prompts that slow down API
    max_context_chars = 3000  # Reduced from unlimited to 3000 chars
    if len(pdf_context) > max_context_chars:
        pdf_context = pdf_context[:max_context_chars] + "\n...[Context truncated for performance]"
    
    return (
        f"You are an expert agricultural assistant. Use the following knowledge base to answer questions:\n\n"
        f"{pdf_context}\n\n"
        f"User Question: {user_query}\n\n"
        "Answer the question directly and naturally. Use the knowledge base above to provide accurate information, "
        "but respond as if you naturally know this information - don't mention 'the document' or 'according to the document'. "
        "If the knowledge base doesn't contain relevant information, use your general agricultural knowledge to help the user."
    )


def generate_gemini_response(user_query: str, pdf_context: str, model_overrides: Optional[List[str]] = None) -> str:
    _ensure_models_loaded()
    prompt = _build_prompt(user_query, pdf_context)
    if not _GEMINI_READY:
        return (
            "Gemini service is unavailable right now. Based on the documents, here's a drafted response:\n\n"
            f"{prompt}"
        )

    candidate_models: List[str] = []
    seen = set()
    preferred = [GEMINI_MODEL, "gemini-2.5-flash", "gemini-flash-latest", "gemini-1.5-flash", "gemini-pro"]

    for model_name in preferred + (model_overrides or []) + AVAILABLE_GEMINI_MODELS:
        if not model_name:
            continue
        normalized = model_name.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidate_models.append(normalized)

    if not candidate_models:
        return (
            "Gemini request failed. Falling back to context summary.\n\n"
            "Reason: No Gemini models supporting generateContent were found for this API key."
            " Ensure the Generative Language API is enabled and the key has access.\n\n"
            f"Prompt used:\n{prompt}"
        )

    last_exception: Optional[Exception] = None
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
        except Exception as exc:
            last_exception = exc
            continue

        if hasattr(response, "text") and response.text:
            return response.text.strip()

        candidates = getattr(response, "candidates", []) or []
        collected_parts: List[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []):
                text = getattr(part, "text", None)
                if text:
                    collected_parts.append(text)
        if collected_parts:
            return "\n\n".join(collected_parts).strip()

    reason = last_exception if last_exception else "No Gemini models returned usable text."
    return (
        "Gemini request failed. Falling back to context summary.\n\n"
        f"Reason: {reason}\n\nPrompt used:\n{prompt}"
    )


def generate_gemini_response_stream(user_query: str, pdf_context: str, model_overrides: Optional[List[str]] = None) -> Generator[str, None, None]:
    """Stream Gemini response in real-time for faster perceived performance."""
    _ensure_models_loaded()
    prompt = _build_prompt(user_query, pdf_context)

    if not _GEMINI_READY:
        yield "Gemini service is unavailable right now."
        return

    candidate_models: List[str] = []
    seen = set()
    preferred = [GEMINI_MODEL, "gemini-2.5-flash", "gemini-flash-latest", "gemini-1.5-flash", "gemini-pro"]

    for model_name in preferred + (model_overrides or []) + AVAILABLE_GEMINI_MODELS:
        if not model_name:
            continue
        normalized = model_name.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidate_models.append(normalized)

    if not candidate_models:
        yield "Gemini request failed. No models available."
        return

    last_exception: Optional[Exception] = None
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            # Enable streaming with stream=True and optimize generation config
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 2048,  # Increased from 1024 to allow longer responses
            }
            response = model.generate_content(prompt, stream=True, generation_config=generation_config)
            
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    yield chunk.text
            return  # Successfully streamed
            
        except Exception as exc:
            last_exception = exc
            continue

    # If all models failed
    yield f"Gemini request failed: {last_exception}"


def analyze_plant_disease_image(
    image_bytes: bytes,
    mime_type: str,
    model_overrides: Optional[List[str]] = None,
) -> str:
    """Analyze a plant image and return likely disease diagnosis and treatment guidance."""
    if not image_bytes:
        return "Please upload a valid plant image so I can analyze it."

    normalized_mime = (mime_type or "").strip().lower()
    if normalized_mime not in SUPPORTED_IMAGE_MIME_TYPES:
        return "Unsupported image type. Please upload a JPG, PNG, or WEBP image."

    _ensure_models_loaded()
    if not _GEMINI_READY:
        return (
            "Image diagnosis is temporarily unavailable because Gemini is not configured. "
            "Set GEMINI_API_KEY and try again."
        )

    prompt = (
        "You are an expert agricultural plant pathologist. Analyze the uploaded plant image. "
        "If there are visible symptoms, identify the most likely disease or pest issue. "
        "Respond in clear farmer-friendly language with these sections:\n"
        "1) Likely condition\n"
        "2) Why this diagnosis (visible signs)\n"
        "3) Immediate steps (today/this week)\n"
        "4) Treatment options (organic and chemical if needed)\n"
        "5) Prevention for next season\n"
        "6) When to contact a local agriculture expert\n\n"
        "If the image quality is unclear or no disease is visible, say that explicitly and ask for a clearer "
        "leaf/stem close-up and whole-plant photo before concluding."
    )

    candidate_models: List[str] = []
    seen = set()
    preferred = [
        GEMINI_MODEL,
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-1.5-flash",
        "gemini-pro",
    ]

    for model_name in preferred + (model_overrides or []) + AVAILABLE_GEMINI_MODELS:
        if not model_name:
            continue
        normalized = model_name.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidate_models.append(normalized)

    if not candidate_models:
        return "No Gemini multimodal models are available for this API key."

    last_exception: Optional[Exception] = None
    image_part = {"mime_type": normalized_mime, "data": image_bytes}

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, image_part])
        except Exception as exc:
            last_exception = exc
            continue

        if hasattr(response, "text") and response.text:
            return response.text.strip()

        candidates = getattr(response, "candidates", []) or []
        collected_parts: List[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []):
                text = getattr(part, "text", None)
                if text:
                    collected_parts.append(text)
        if collected_parts:
            return "\n\n".join(collected_parts).strip()

    return f"Image diagnosis failed: {last_exception or 'No model returned a usable response.'}"
