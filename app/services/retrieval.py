"""TF-IDF retrieval over the knowledge base: cheap candidate search before the LLM judges relevance."""
import threading

from app.repositories import kb_repo

_lock = threading.Lock()
_state = {"dirty": True, "vec": None, "matrix": None, "docs": []}


def invalidate():
    """Mark the cached index stale; it is rebuilt lazily on the next search."""
    _state["dirty"] = True


def _ensure_built():
    from sklearn.feature_extraction.text import TfidfVectorizer

    with _lock:
        if not _state["dirty"]:
            return
        docs = kb_repo.list_all()
        if docs:
            vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=5000)
            _state.update(vec=vec, matrix=vec.fit_transform([f"{d['title']} {d['content']}" for d in docs]), docs=docs)
        else:
            _state.update(vec=None, matrix=None, docs=[])
        _state["dirty"] = False


def warm_up():
    """Build the index at startup so the first user search is fast."""
    _ensure_built()


def search(query, k=5, exclude_ids=()):
    """Return [(doc, score)] best matches first (score > 0 only)."""
    from sklearn.metrics.pairwise import cosine_similarity

    _ensure_built()
    if not query or not query.strip() or _state["vec"] is None:
        return []
    sims = cosine_similarity(_state["vec"].transform([query]), _state["matrix"])[0]
    ranked = sorted(zip(_state["docs"], sims), key=lambda p: -p[1])
    return [(d, float(s)) for d, s in ranked if s > 0 and d["_id"] not in exclude_ids][:k]


def title_similarity(new_texts, existing_texts):
    """Cosine similarity matrix [len(new) x len(existing)] using TF-IDF fitted on both sets."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if not new_texts or not existing_texts:
        return []
    vec = TfidfVectorizer(stop_words="english").fit(list(new_texts) + list(existing_texts))
    return cosine_similarity(vec.transform(new_texts), vec.transform(existing_texts))
