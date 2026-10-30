"""TF-IDF retrieval over the knowledge base (expanded in Phase 3)."""
_dirty = True


def invalidate():
    """Mark the cached index stale; it is rebuilt lazily on next search."""
    global _dirty
    _dirty = True


def title_similarity(new_texts, existing_texts):
    """Cosine similarity matrix [len(new) x len(existing)] using TF-IDF fitted on both sets."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if not new_texts or not existing_texts:
        return []
    vec = TfidfVectorizer(stop_words="english").fit(list(new_texts) + list(existing_texts))
    return cosine_similarity(vec.transform(new_texts), vec.transform(existing_texts))
