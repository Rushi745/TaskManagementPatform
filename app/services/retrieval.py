"""TF-IDF retrieval over the knowledge base (expanded in Phase 3)."""
_dirty = True


def invalidate():
    """Mark the cached index stale; it is rebuilt lazily on next search."""
    global _dirty
    _dirty = True
