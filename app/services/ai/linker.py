"""Link action items / meetings to knowledge-base docs: TF-IDF candidates -> LLM judgement -> id check."""
import logging

from app.logging_setup import log_event
from app.repositories import items_repo, kb_repo, meetings_repo
from app.schemas.ai import LinkOut
from app.services import item_service, meeting_service, retrieval
from app.services.ai import prompts, with_fallback
from app.services.ai.llm_client import generate_json
from app.utils import oid

log = logging.getLogger("app.ai")
FALLBACK_MIN_SCORE = 0.15


def _link(doc, reason, method):
    return {"doc_id": doc["_id"], "title": doc["title"], "reason": reason, "method": method}


def find_links(kind, text, exclude_ids=()):
    """Return (links, source). The LLM may only choose among the TF-IDF candidates (hallucinated ids are dropped)."""
    cands = retrieval.search(text, k=5, exclude_ids=exclude_ids)
    if not cands:
        return [], "ai"
    by_id = {str(d["_id"]): d for d, _ in cands}

    def ai():
        listing = "\n".join(f"{i} | {d['title']} | {d['content'][:300].replace(chr(10), ' ')}" for i, d in by_id.items())
        out = generate_json("link", prompts.LINK_PROMPT.format(kind=kind, text=text[:3000], candidates=listing), LinkOut)
        seen, links = set(), []
        for dec in out.links:
            if dec.relevant and dec.doc_id in by_id and dec.doc_id not in seen:  # id check: no invented documents
                seen.add(dec.doc_id)
                links.append(_link(by_id[dec.doc_id], dec.reason.strip(), "ai"))
        return links

    def fallback():
        return [_link(d, "Keyword similarity (AI unavailable)", "tfidf") for d, s in cands[:3] if s >= FALLBACK_MIN_SCORE]

    return with_fallback("link", ai, fallback)


def link_item(item_id):
    """Find related docs for an item and save them on it."""
    it = item_service.get_item(item_id)
    links, source = find_links("action item", f"{it['title']}. {it.get('description') or ''}")
    items_repo.apply(it["_id"], set_fields={"kb_links": links})
    log_event(log, "kb.linked", target="item", item_id=str(it["_id"]), links=len(links), source=source)
    return {"kb_links": links, "source": source}


def link_meeting(meeting_id):
    """Find related docs for a meeting (excluding its own auto-indexed doc) and save them on it."""
    m = meeting_service.get_meeting(meeting_id)
    own = kb_repo.find_by_meeting(m["_id"])
    text = " ".join([m["title"], m.get("summary") or ""] + [d["text"] for d in m.get("decisions", [])])
    links, source = find_links("meeting", text, exclude_ids={own["_id"]} if own else ())
    meetings_repo.update(m["_id"], {"kb_links": links})
    log_event(log, "kb.linked", target="meeting", meeting_id=str(m["_id"]), links=len(links), source=source)
    return {"kb_links": links, "source": source}
