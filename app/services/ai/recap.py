"""AI recap: raw notes -> reviewable draft (summary, decisions, items) with deterministic post-checks."""
import logging
from datetime import datetime, timedelta

from app.errors import ValidationFailed
from app.schemas.ai import RecapOut
from app.services import item_service, meeting_service, retrieval
from app.services.ai import prompts, with_fallback
from app.services.ai.fallback import recap_fallback
from app.services.ai.llm_client import generate_json
from app.logging_setup import log_event
from app.utils import parse_date, today_start

log = logging.getLogger("app.ai")
MIN_NOTES = 20
DUP_THRESHOLD = 0.8
LOW_CONFIDENCE = 0.6


def _resolve_owner(name, participants):
    """Owner grounding: accept a participant's full name (any case) or a unique first name, else None."""
    if not name:
        return None
    n = name.strip().lower()
    for p in participants:
        if p["name"].lower() == n:
            return p
    matches = [p for p in participants if p["name"].split()[0].lower() == n]
    return matches[0] if len(matches) == 1 else None


def post_validate(data, participants, open_items):
    """Apply the deterministic checks to model/fallback output and shape the UI draft.

    1) owner must be a participant  2) date must parse and be within a year  3) low confidence -> review
    4) near-duplicate of an existing open item is flagged."""
    today = today_start()
    items = []
    for raw in data["action_items"]:
        needs_review = raw["confidence"] < LOW_CONFIDENCE
        owner = _resolve_owner(raw.get("owner"), participants)
        if raw.get("owner") and not owner:
            needs_review = True  # model named someone who is not a participant
        due = None
        if raw.get("due_date"):
            try:
                d = parse_date(raw["due_date"])
                if abs(d - today) > timedelta(days=365):
                    needs_review = True
                else:
                    due = d.strftime("%Y-%m-%d")
            except ValidationFailed:
                needs_review = True
        items.append({
            "title": raw["title"].strip(), "description": "",
            "owner_id": str(owner["person_id"]) if owner else None, "owner_name": owner["name"] if owner else None,
            "due_date": due, "priority": raw.get("priority", "medium"), "evidence": raw.get("evidence", ""),
            "confidence": raw["confidence"], "needs_review": needs_review, "possible_duplicate_of": None,
        })
    if items and open_items:
        sims = retrieval.title_similarity([i["title"] for i in items], [o["title"] for o in open_items])
        for i, row in enumerate(sims):
            j = int(row.argmax())
            if row[j] > DUP_THRESHOLD:
                items[i]["possible_duplicate_of"] = {"id": str(open_items[j]["_id"]), "title": open_items[j]["title"]}
    return {"summary": data["summary"], "decisions": data["decisions"], "open_questions": data.get("open_questions", []), "items": items}


def generate_draft(meeting_id, raw_notes=None):
    """Return a recap DRAFT (nothing is saved). source is 'ai' or 'fallback'."""
    m = meeting_service.get_meeting(meeting_id)
    notes = (raw_notes if raw_notes is not None else m.get("raw_notes") or "").strip()
    if len(notes) < MIN_NOTES:
        raise ValidationFailed([{"field": "raw_notes", "msg": f"Add at least {MIN_NOTES} characters of notes first"}])
    parts = m["participants"]
    open_items = item_service.list_items(status="active")
    log_event(log, "recap.requested", meeting_id=str(m["_id"]), notes_chars=len(notes))

    def ai():
        prompt = prompts.RECAP_PROMPT.format(
            today=today_start().strftime("%Y-%m-%d"), meeting_date=m["date"].strftime("%Y-%m-%d"),
            participant_names=", ".join(p["name"] for p in parts) or "(none)",
            open_item_titles="; ".join(i["title"] for i in open_items[:30]) or "(none)", raw_notes=notes)
        return post_validate(generate_json("recap", prompt, RecapOut).model_dump(), parts, open_items)

    draft, source = with_fallback("recap", ai, lambda: post_validate(recap_fallback(notes, parts), parts, open_items))
    draft["source"] = source
    draft["warning"] = "AI unavailable — basic extraction used. Please review carefully." if source == "fallback" else None
    return draft
