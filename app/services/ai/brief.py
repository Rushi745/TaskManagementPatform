"""AI catch-up brief for someone who missed a meeting or is taking over work."""
import logging

from app.logging_setup import log_event
from app.repositories import briefs_repo
from app.schemas.ai import BriefOut
from app.services import item_service, meeting_service, people_service
from app.services.ai import prompts, with_fallback
from app.services.ai.fallback import brief_fallback
from app.services.ai.llm_client import generate_json
from app.utils import utcnow

log = logging.getLogger("app.ai")


def _fmt(i):
    return f"{i['title']} | {i.get('owner_name') or 'unassigned'} | {i['due_date'].strftime('%Y-%m-%d') if i.get('due_date') else 'no date'} | {i['status']}"


def generate_brief(meeting_id, person_id, mode="missed"):
    """Build (and store) a short brief tailored to one person. Falls back to a template without AI."""
    m = meeting_service.get_meeting(meeting_id)
    person = people_service.get_person(person_id)
    items = item_service.list_items(meeting_id=str(m["_id"]))
    own = [i for i in items if i.get("owner_id") == person["_id"]]
    docs = [l["title"] for l in m.get("kb_links", [])]

    def ai():
        prompt = prompts.BRIEF_PROMPT.format(
            person_name=person["name"], role=person.get("role") or "team member",
            reason="missed this meeting" if mode == "missed" else "is taking over this work",
            title=m["title"], date=m["date"].strftime("%Y-%m-%d"), summary=m.get("summary") or "(no summary)",
            decisions="; ".join(d["text"] for d in m.get("decisions", [])) or "(none)",
            items="\n".join(_fmt(i) for i in items) or "(none)", own_items="\n".join(_fmt(i) for i in own) or "(none)",
            doc_titles=", ".join(docs) or "(none)")
        return generate_json("brief", prompt, BriefOut).model_dump()

    content, source = with_fallback("brief", ai, lambda: brief_fallback(person["name"], m, own, items))
    briefs_repo.insert({"kind": "catchup", "meeting_id": m["_id"], "person_id": person["_id"], "content": content, "source": source, "created_at": utcnow()})
    log_event(log, "brief.generated", meeting_id=str(m["_id"]), person=person["name"], source=source)
    return {"person": person["name"], "content": content, "source": source}
