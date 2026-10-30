"""Meeting / handover use-cases: create, edit, lifecycle, carry-forward."""
import logging

from app.errors import Conflict, NotFound, ValidationFailed
from app.logging_setup import log_event
from app.repositories import items_repo, meetings_repo, people_repo
from app.schemas.meeting import MeetingCreate, MeetingUpdate, RecapApply
from app.services import item_service, kb_service
from app.utils import oid, parse_date, utcnow

log = logging.getLogger("app.meetings")
TRANSITIONS = {"scheduled": {"completed", "archived"}, "completed": {"archived"}, "archived": set()}


def _participants(ids):
    """Resolve participant ids to embedded participant docs (attended defaults to False)."""
    oids = [oid(i, "Person") for i in dict.fromkeys(ids)]
    found = {p["_id"]: p for p in people_repo.get_many(oids)}
    missing = [str(i) for i in oids if i not in found]
    if missing:
        raise ValidationFailed([{"field": "participant_ids", "msg": "Unknown participant"}])
    return [{"person_id": i, "name": found[i]["name"], "attended": False} for i in oids]


def get_meeting(meeting_id):
    """Fetch a meeting or raise NotFound."""
    m = meetings_repo.get(oid(meeting_id, "Meeting"))
    if not m:
        raise NotFound("Meeting not found")
    return m


def create_meeting(data: MeetingCreate, actor="system"):
    """Create a meeting or handover record in `scheduled` state."""
    now = utcnow()
    doc = {
        "type": data.type, "title": data.title, "date": parse_date(data.date), "status": "scheduled",
        "agenda": data.agenda, "participants": _participants(data.participant_ids),
        "raw_notes": data.raw_notes, "summary": None, "decisions": [], "recap_source": None,
        "previous_meeting_id": None, "kb_links": [], "created_at": now, "updated_at": now,
    }
    if data.type == "handover":
        doc["handover"] = {"from_person_id": oid(data.from_person_id, "Person"),
                           "to_person_id": oid(data.to_person_id, "Person") if data.to_person_id else None,
                           "reason": "leave", "brief": "", "item_ids": []}
    doc["_id"] = meetings_repo.insert(doc)
    log_event(log, "meeting.created", meeting_id=str(doc["_id"]), type=data.type, by=actor, notes_chars=len(data.raw_notes))
    return doc


def list_meetings(type_=None, status=None):
    """Meetings newest first, each with its count of open items."""
    q = {}
    if type_:
        q["type"] = type_
    if status:
        q["status"] = status
    meetings = meetings_repo.list_filtered(q)
    active = items_repo.find({"status": {"$in": item_service.ACTIVE}})
    for m in meetings:
        m["open_items"] = sum(1 for i in active if m["_id"] in i.get("meeting_ids", []))
    return meetings


def get_detail(meeting_id):
    """Meeting plus its action items and previous-meeting info."""
    m = get_meeting(meeting_id)
    items = item_service.list_items(meeting_id=str(m["_id"]))
    prev = meetings_repo.get(m["previous_meeting_id"]) if m.get("previous_meeting_id") else None
    m["previous_meeting"] = {"_id": prev["_id"], "title": prev["title"]} if prev else None
    m["items"] = items
    return m


def update_meeting(meeting_id, data: MeetingUpdate, actor="system"):
    """Edit agenda/notes/summary/decisions/attendance; re-index KB if already completed."""
    m = get_meeting(meeting_id)
    sent = data.model_fields_set
    fields = {}
    for k in ("title", "agenda", "raw_notes", "summary"):
        if k in sent and getattr(data, k) is not None:
            fields[k] = getattr(data, k)
    if "date" in sent and data.date:
        fields["date"] = parse_date(data.date)
    if "decisions" in sent and data.decisions is not None:
        fields["decisions"] = [d.model_dump() for d in data.decisions]
    if "attendance" in sent and data.attendance is not None:
        parts = m["participants"]
        for p in parts:
            key = str(p["person_id"])
            if key in data.attendance:
                p["attended"] = data.attendance[key]
        fields["participants"] = parts
    if fields:
        fields["updated_at"] = utcnow()
        meetings_repo.update(m["_id"], fields)
        m = get_meeting(meeting_id)
        if m["status"] == "completed":
            kb_service.index_meeting(m, item_service.list_items(meeting_id=str(m["_id"])))
    return m


def change_status(meeting_id, new_status, actor="system"):
    """Lifecycle: scheduled -> completed -> archived. Completing needs a title and a participant."""
    m = get_meeting(meeting_id)
    if new_status == m["status"] or new_status not in TRANSITIONS[m["status"]]:
        raise Conflict(f"Cannot move a {m['status']} meeting to {new_status}.")
    if new_status == "completed" and not (m.get("title") and m.get("participants")):
        raise Conflict("A meeting needs a title and at least one participant before it can be completed.")
    meetings_repo.update(m["_id"], {"status": new_status, "updated_at": utcnow()})
    log_event(log, "meeting.status_changed", meeting_id=str(m["_id"]), type=m["type"], **{"from": m["status"], "to": new_status}, by=actor)
    m = get_meeting(meeting_id)
    if new_status == "completed":
        kb_service.index_meeting(m, item_service.list_items(meeting_id=str(m["_id"])))
    return m


def create_next(meeting_id, title, date, actor="system"):
    """Create the next meeting and carry every open item forward (one item record, history kept)."""
    src = get_meeting(meeting_id)
    if src["status"] != "completed":
        raise Conflict("Only a completed meeting can be carried forward.")
    if meetings_repo.find_next_of(src["_id"]):
        raise Conflict("A next meeting already exists for this meeting.")
    carried = [i for i in items_repo.find({"meeting_ids": src["_id"], "status": {"$in": item_service.ACTIVE}})
               if i["meeting_ids"][-1] == src["_id"]]
    carried.sort(key=lambda i: i["created_at"])
    now = utcnow()
    new = {
        "type": src["type"], "title": title, "date": parse_date(date), "status": "scheduled",
        "agenda": [f"Review: {i['title']}" for i in carried],
        "participants": [{**p, "attended": False} for p in src["participants"]],
        "raw_notes": "", "summary": None, "decisions": [], "recap_source": None,
        "previous_meeting_id": src["_id"], "kb_links": [], "created_at": now, "updated_at": now,
    }
    new["_id"] = meetings_repo.insert(new)
    for it in carried:
        ev = item_service.event("carried_forward", actor, str(src["_id"]), str(new["_id"]), f"Carried from {src['title']}")
        items_repo.apply(it["_id"], set_fields={"updated_at": now}, push_events=[ev], push_meeting=new["_id"])
        log_event(log, "item.carried_forward", item_id=str(it["_id"]), from_meeting_id=str(src["_id"]), to_meeting_id=str(new["_id"]))
    log_event(log, "meeting.next_created", from_meeting_id=str(src["_id"]), new_meeting_id=str(new["_id"]), carried_count=len(carried))
    new["carried_count"] = len(carried)
    return new


def apply_recap(meeting_id, data: RecapApply, actor="system"):
    """Save a reviewed recap: summary, decisions and the accepted action items."""
    m = get_meeting(meeting_id)
    meetings_repo.update(m["_id"], {
        "summary": data.summary or None,
        "decisions": [{"text": d.strip(), "made_by": None} for d in data.decisions if d.strip()],
        "recap_source": data.source, "updated_at": utcnow()})
    created = [item_service.create_item(
        title=i.title, meeting_id=str(m["_id"]), owner_id=i.owner_id, due_date=i.due_date, priority=i.priority,
        description=i.description, source=data.source, evidence=i.evidence, needs_review=i.needs_review, actor=actor)
        for i in data.items]
    m = get_meeting(meeting_id)
    if m["status"] == "completed":
        kb_service.index_meeting(m, item_service.list_items(meeting_id=str(m["_id"])))
    log_event(log, "recap.applied", meeting_id=str(m["_id"]), source=data.source, items=len(created), decisions=len(data.decisions))
    return {"meeting": m, "created_items": created}
