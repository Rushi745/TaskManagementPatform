"""Knowledge base use-cases (expanded in Phase 3). Phase 1 only needs meeting indexing."""
import logging

from app.logging_setup import log_event
from app.repositories import kb_repo
from app.services import retrieval
from app.utils import utcnow

log = logging.getLogger("app.kb")


def index_meeting(meeting, items=()):
    """Upsert a completed meeting's summary + decisions into the KB (source='meeting')."""
    lines = [meeting.get("summary") or ""]
    lines += [f"Decision: {d['text']}" for d in meeting.get("decisions", [])]
    lines += [f"Action: {i['title']}" for i in items]
    content = "\n".join(l for l in lines if l).strip() or meeting["title"]
    existing = kb_repo.find_by_meeting(meeting["_id"])
    if existing:
        kb_repo.update(existing["_id"], {"title": meeting["title"], "content": content})
        doc_id = existing["_id"]
    else:
        doc_id = kb_repo.insert({"title": meeting["title"], "content": content, "tags": ["meeting"],
                                 "source": "meeting", "meeting_id": meeting["_id"], "created_at": utcnow()})
    retrieval.invalidate()
    log_event(log, "kb.doc_added", doc_id=str(doc_id), source="meeting", chars=len(content))


def _excerpt(doc, n=220):
    doc["excerpt"] = doc["content"][:n] + ("…" if len(doc["content"]) > n else "")
    return doc


def list_docs(q=None):
    """All docs (newest first) or, with q, ranked keyword matches."""
    if q and q.strip():
        return [dict(_excerpt(d), score=round(s, 3)) for d, s in retrieval.search(q, k=20)]
    return [_excerpt(d) for d in kb_repo.list_all()]


def get_doc(doc_id):
    """One doc with backlinks: items and meetings that were linked to it."""
    from app.errors import NotFound
    from app.repositories import items_repo, meetings_repo
    from app.utils import oid

    d = kb_repo.get(oid(doc_id, "Document"))
    if not d:
        raise NotFound("Document not found")
    d["linked_items"] = [{"id": i["_id"], "title": i["title"], "status": i["status"]} for i in items_repo.find({"kb_links.doc_id": d["_id"]})]
    d["linked_meetings"] = [{"id": m["_id"], "title": m["title"]} for m in meetings_repo.list_filtered({"kb_links.doc_id": d["_id"]})]
    return d


def add_doc(data, source="manual"):
    """Add a pasted-text document to the knowledge base."""
    doc = {"title": data.title, "content": data.content, "tags": data.tags, "source": source, "meeting_id": None, "created_at": utcnow()}
    doc["_id"] = kb_repo.insert(doc)
    retrieval.invalidate()
    log_event(log, "kb.doc_added", doc_id=str(doc["_id"]), source=source, chars=len(data.content))
    return doc
