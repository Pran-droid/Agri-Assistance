import os
from typing import List, Optional, Generator
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

_client = None
_GEMINI_READY = False


def _get_client():
    """Lazily initialize the Gemini client on first use."""
    global _client, _GEMINI_READY
    if _client is not None:
        return _client
    if not GEMINI_API_KEY or not GENAI_AVAILABLE:
        return None
    try:
        _client = genai.Client(api_key=GEMINI_API_KEY)
        _GEMINI_READY = True
        return _client
    except Exception as e:
        print(f"⚠️  Failed to initialize Gemini client: {e}")
        _GEMINI_READY = False
        return None


def _build_prompt(user_query: str, pdf_context: str) -> str:
    max_context_chars = 3000
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


def _get_candidate_models() -> List[str]:
    preferred = [GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    seen = set()
    result = []
    for m in preferred:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def generate_gemini_response(user_query: str, pdf_context: str, model_overrides: Optional[List[str]] = None) -> str:
    client = _get_client()
    prompt = _build_prompt(user_query, pdf_context)

    if not client:
        return (
            "Gemini service is unavailable right now. Please check your GEMINI_API_KEY.\n\n"
            f"Prompt used:\n{prompt}"
        )

    candidate_models = _get_candidate_models()
    if model_overrides:
        candidate_models = model_overrides + candidate_models

    last_exception = None
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response.text:
                return response.text.strip()
        except Exception as exc:
            last_exception = exc
            continue

    return (
        "Gemini request failed. Falling back to context summary.\n\n"
        f"Reason: {last_exception or 'No model returned a usable response.'}"
    )


def generate_gemini_response_stream(user_query: str, pdf_context: str, model_overrides: Optional[List[str]] = None) -> Generator[str, None, None]:
    """Stream Gemini response in real-time for faster perceived performance."""
    client = _get_client()
    prompt = _build_prompt(user_query, pdf_context)

    if not client:
        yield "Gemini service is unavailable right now."
        return

    candidate_models = _get_candidate_models()
    if model_overrides:
        candidate_models = model_overrides + candidate_models

    last_exception = None
    for model_name in candidate_models:
        try:
            for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=2048,
                ) if types else None,
            ):
                if chunk.text:
                    yield chunk.text
            return  # Successfully streamed
        except Exception as exc:
            last_exception = exc
            continue

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

    client = _get_client()
    if not client:
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

    candidate_models = _get_candidate_models()
    if model_overrides:
        candidate_models = model_overrides + candidate_models

    last_exception = None
    for model_name in candidate_models:
        try:
            if types:
                image_part = types.Part.from_bytes(data=image_bytes, mime_type=normalized_mime)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, image_part],
                )
            else:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, {"mime_type": normalized_mime, "data": image_bytes}],
                )
            if response.text:
                return response.text.strip()
        except Exception as exc:
            last_exception = exc
            continue

    return f"Image diagnosis failed: {last_exception or 'No model returned a usable response.'}"
