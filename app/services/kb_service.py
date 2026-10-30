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
