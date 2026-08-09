import os
from knowledge_base import FAQ_POLICIES

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Globals for lazy loading
_vectorizer = None
_faq_matrix = None

SIMILARITY_THRESHOLD = 0.15  # Decreased to allow colloquial queries to match formal policy text

def _initialize_engine():
    """Initializes the TF-IDF vectorizer and encodes the knowledge base."""
    global _vectorizer, _faq_matrix
    if _vectorizer is not None:
        return _vectorizer, _faq_matrix
        
    try:
        print("[RAG] Initializing Local TF-IDF Search Engine...")
        # Combine title + text so queries can match on both (e.g. "payment methods")
        texts = [f"{doc['title']}. {doc['text']}" for doc in FAQ_POLICIES]
        
        # We use character n-grams to handle typos and sub-word matches
        _vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer='word', stop_words='english')
        _faq_matrix = _vectorizer.fit_transform(texts)
        
        return _vectorizer, _faq_matrix
    except Exception as e:
        print(f"[RAG] FAILED to initialize local engine: {e}")
        return None, None

def retrieve_answer(query: str) -> dict:
    """
    Vectorizes the user query using TF-IDF and performs Cosine Similarity against the knowledge base.
    Returns the document dictionary if a match is found, else None.
    """
    vectorizer, faq_matrix = _initialize_engine()
    if not vectorizer or faq_matrix is None:
        return None

    try:
        # Embed the incoming user query
        query_vector = vectorizer.transform([query])
        
        # Compute cosine similarity
        similarities = cosine_similarity(query_vector, faq_matrix).flatten()
        
        # Find the top match
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]

        if best_score >= SIMILARITY_THRESHOLD:
            best_doc = FAQ_POLICIES[best_idx]
            print(f"[RAG] Match found: '{best_doc['title']}' (Score: {best_score:.4f})")
            return {
                "id": best_doc.get("id"),
                "title": best_doc["title"],
                "text": best_doc["text"],
                "score": float(best_score)
            }
    except Exception as e:
        print(f"[RAG] Search error: {e}")
    
    return None

