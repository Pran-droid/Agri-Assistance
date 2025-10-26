from deep_translator import GoogleTranslator


def translate_text(text: str, src_language: str = "auto", dest_language: str = "en") -> str:
    if not text:
        return ""
    if src_language == dest_language:
        return text
    source_lang = None if src_language == "auto" else src_language
    try:
        translator = GoogleTranslator(source=source_lang, target=dest_language)
        return translator.translate(text)
    except Exception:
        return text
