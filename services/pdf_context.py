import os
import pickle
from typing import List, Tuple, Dict
import numpy as np

from PyPDF2 import PdfReader

# Try to import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("⚠️  sentence-transformers not installed. Run: pip install sentence-transformers")

PDF_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pdfs")
PDF_DIRECTORY = os.path.abspath(PDF_DIRECTORY)
CACHE_FILE = os.path.join(PDF_DIRECTORY, ".pdf_embeddings_cache.pkl")

# Global cache for embeddings
_PDF_CACHE: Dict[str, any] = {
    "paragraphs": [],
    "embeddings": None,
    "model": None,
    "loaded": False
}


def _load_pdfs_and_create_embeddings():
    """Load all PDFs and create vector embeddings once at startup."""
    if _PDF_CACHE["loaded"]:
        return
    
    print("🔄 Loading PDFs and creating embeddings...")
    
    if not os.path.isdir(PDF_DIRECTORY):
        print(f"⚠️  PDF directory not found: {PDF_DIRECTORY}")
        _PDF_CACHE["loaded"] = True
        return
    
    # Try to load from cache first
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'rb') as f:
                cache_data = pickle.load(f)
                _PDF_CACHE["paragraphs"] = cache_data["paragraphs"]
                _PDF_CACHE["embeddings"] = cache_data["embeddings"]
                print(f"✅ Loaded {len(_PDF_CACHE['paragraphs'])} paragraphs from cache")
                _PDF_CACHE["loaded"] = True
                
                # Load embedding model
                if EMBEDDINGS_AVAILABLE:
                    _PDF_CACHE["model"] = SentenceTransformer('all-MiniLM-L6-v2')
                return
        except Exception as e:
            print(f"⚠️  Failed to load cache: {e}")
    
    # Load PDFs from scratch
    all_paragraphs = []
    
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
            
            # Split into paragraphs
            paragraphs = [para.strip() for para in full_text.split("\n\n") if para.strip() and len(para.strip()) > 50]
            all_paragraphs.extend(paragraphs)
            print(f"📄 Loaded {filename}: {len(paragraphs)} paragraphs")
        except Exception as e:
            print(f"⚠️  Error loading {filename}: {e}")
            continue
    
    _PDF_CACHE["paragraphs"] = all_paragraphs
    print(f"📚 Total paragraphs loaded: {len(all_paragraphs)}")
    
    # Create embeddings if available
    if EMBEDDINGS_AVAILABLE and all_paragraphs:
        try:
            print("🧠 Creating embeddings...")
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embeddings = model.encode(all_paragraphs, show_progress_bar=True)
            _PDF_CACHE["embeddings"] = embeddings
            _PDF_CACHE["model"] = model
            
            # Save to cache
            cache_data = {
                "paragraphs": all_paragraphs,
                "embeddings": embeddings
            }
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(cache_data, f)
            print(f"💾 Embeddings cached to {CACHE_FILE}")
        except Exception as e:
            print(f"⚠️  Error creating embeddings: {e}")
    
    _PDF_CACHE["loaded"] = True
    print("✅ PDF indexing complete!")


def _cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def _collect_keywords(query: str) -> List[str]:
    return [word.strip().lower() for word in query.split() if len(word) > 2]


def _score_paragraphs(paragraphs: List[str], keywords: List[str]) -> List[Tuple[int, str]]:
    scored = []
    for paragraph in paragraphs:
        score = sum(1 for keyword in keywords if keyword in paragraph.lower())
        if score:
            scored.append((score, paragraph))
    return scored


def get_context_from_pdfs(query: str, top_k: int = 2) -> str:
    """
    Retrieve most relevant context from PDFs using RAG with vector embeddings.
    Falls back to keyword matching if embeddings are not available.
    """
    # Ensure PDFs are loaded
    if not _PDF_CACHE["loaded"]:
        _load_pdfs_and_create_embeddings()
    
    if not _PDF_CACHE["paragraphs"]:
        return ""
    
    # Use vector similarity if embeddings are available
    if EMBEDDINGS_AVAILABLE and _PDF_CACHE["embeddings"] is not None and _PDF_CACHE["model"] is not None:
        try:
            # Encode the query
            query_embedding = _PDF_CACHE["model"].encode([query])[0]
            
            # Calculate similarities
            similarities = []
            for i, para_embedding in enumerate(_PDF_CACHE["embeddings"]):
                similarity = _cosine_similarity(query_embedding, para_embedding)
                similarities.append((similarity, _PDF_CACHE["paragraphs"][i]))
            
            # Sort by similarity and get top-k
            similarities.sort(key=lambda x: x[0], reverse=True)
            top_paragraphs = [para for _, para in similarities[:top_k]]
            
            return "\n\n".join(top_paragraphs)
        except Exception as e:
            print(f"⚠️  Error in vector search: {e}, falling back to keyword matching")
    
    # Fallback: Keyword-based matching
    keywords = _collect_keywords(query)
    if not keywords:
        return ""
    
    matches = _score_paragraphs(_PDF_CACHE["paragraphs"], keywords)
    
    if not matches:
        return ""
    
    matches.sort(key=lambda item: item[0], reverse=True)
    top_paragraphs = [para for _, para in matches[:top_k]]
    return "\n\n".join(top_paragraphs)


# Initialize embeddings when module is imported
_load_pdfs_and_create_embeddings()
