import os
from typing import List, Tuple

from PyPDF2 import PdfReader

PDF_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pdfs")
PDF_DIRECTORY = os.path.abspath(PDF_DIRECTORY)


def _collect_keywords(query: str) -> List[str]:
    return [word.strip().lower() for word in query.split() if len(word) > 2]


def _score_paragraphs(paragraphs: List[str], keywords: List[str]) -> List[Tuple[int, str]]:
    scored = []
    for paragraph in paragraphs:
        score = sum(1 for keyword in keywords if keyword in paragraph.lower())
        if score:
            scored.append((score, paragraph))
    return scored


def get_context_from_pdfs(query: str) -> str:
    if not os.path.isdir(PDF_DIRECTORY):
        return ""

    keywords = _collect_keywords(query)
    if not keywords:
        return ""

    matches: List[Tuple[int, str]] = []

    for filename in os.listdir(PDF_DIRECTORY):
        if not filename.lower().endswith(".pdf"):
            continue
        file_path = os.path.join(PDF_DIRECTORY, filename)
        try:
            with open(file_path, "rb") as pdf_file:
                reader = PdfReader(pdf_file)
                text_buffer = []
                for page in reader.pages:
                    text_buffer.append(page.extract_text() or "")
                full_text = "\n".join(text_buffer)
        except Exception:
            continue

        paragraphs = [para.strip() for para in full_text.split("\n\n") if para.strip()]
        matches.extend(_score_paragraphs(paragraphs, keywords))

    if not matches:
        return ""

    matches.sort(key=lambda item: item[0], reverse=True)
    top_paragraphs = [para for _, para in matches[:3]]
    return "\n\n".join(top_paragraphs)
