"""Action item use-cases: lifecycle, history, reassignment."""
import logging

from app.errors import Conflict, NotFound, ValidationFailed
from app.logging_setup import log_event
from app.repositories import items_repo, meetings_repo, people_repo
from app.schemas.item import ItemUpdate
from app.utils import oid, parse_date, request_id, today_start, utcnow

log = logging.getLogger("app.items")
ACTIVE = ["open", "in_progress", "blocked"]
CLOSED = ["done", "dropped"]


def event(kind, by, frm=None, to=None, note=None):
    """Build one history entry."""
    return {"at": utcnow(), "event": kind, "by": by, "from": frm, "to": to, "note": note, "request_id": request_id()}


def decorate(item):
    """Add derived fields (not stored): is_overdue and carry_count."""
    due = item.get("due_date")
    item["is_overdue"] = bool(due and due < today_start() and item["status"] in ACTIVE)
    item["carry_count"] = max(len(item.get("meeting_ids", [])) - 1, 0)
    return item


def _titles(item_list):
    """Attach meeting titles to each item in one query."""
    ids = {m for it in item_list for m in it.get("meeting_ids", [])}
    names = {m["_id"]: m["title"] for m in meetings_repo.get_many(list(ids))}
    for it in item_list:
        it["meeting_titles"] = [names.get(m, "?") for m in it.get("meeting_ids", [])]
        it["origin_meeting_title"] = names.get(it.get("origin_meeting_id"), "?")
    return item_list


def _owner(owner_id):
    """Resolve an owner id to (ObjectId, name); None -> (None, None)."""
    if not owner_id:
        return None, None
    p = people_repo.get(oid(owner_id, "Owner"))
    if not p:
        raise ValidationFailed([{"field": "owner_id", "msg": "Owner not found"}])
    return p["_id"], p["name"]


def create_item(*, title, meeting_id, owner_id=None, due_date=None, priority="medium", description="",
                source="manual", evidence=None, needs_review=False, actor="system", outcome_note=None):
    """Create an action item attached to a meeting and record the `created` event."""
    mid = oid(meeting_id, "Meeting")
    if not meetings_repo.get(mid):
        raise NotFound("Meeting not found")
    o_id, o_name = _owner(owner_id)
    now = utcnow()
    doc = {
        "title": title, "description": description or "", "owner_id": o_id, "owner_name": o_name,
        "due_date": parse_date(due_date, "due_date") if due_date else None, "priority": priority,
        "status": "open", "outcome": None, "origin_meeting_id": mid, "meeting_ids": [mid],
        "source": source, "evidence": evidence, "needs_review": needs_review, "kb_links": [],
        "history": [event("created", actor, to=o_name, note=f"source: {source}")],
        "closed_at": None, "created_at": now, "updated_at": now,
    }
    doc["_id"] = items_repo.insert(doc)
    log_event(log, "item.created", item_id=str(doc["_id"]), meeting_id=str(mid), owner=o_name, source=source)
    return decorate(doc)


def get_item(item_id):
    """Fetch one item (with history and meeting titles) or raise NotFound."""
    it = items_repo.get(oid(item_id, "Item"))
    if not it:
        raise NotFound("Item not found")
    return _titles([decorate(it)])[0]


def list_items(status=None, owner_id=None, overdue=False, meeting_id=None):
    """Filtered item list, soonest due first (undated last)."""
    q = {}
    if status == "active":
        q["status"] = {"$in": ACTIVE}
    elif status:
        q["status"] = status
    if owner_id:
        q["owner_id"] = oid(owner_id, "Owner")
    if meeting_id:
        q["meeting_ids"] = oid(meeting_id, "Meeting")
    if overdue:
        q["due_date"] = {"$lt": today_start()}
        q["status"] = {"$in": ACTIVE}
    items = [decorate(i) for i in items_repo.find(q)]
    items.sort(key=lambda i: (i["due_date"] is None, i["due_date"] or utcnow()))
    return _titles(items)


def update_item(item_id, data: ItemUpdate, actor):
    """Change status (non-closing), owner, due date or priority; every change is logged in history."""
    it = get_item(item_id)
    if it["status"] in CLOSED:
        raise Conflict("This item is closed. Reopen it before changing it.")
    sent = data.model_fields_set
    sets, events = {}, []

    if "status" in sent and data.status and data.status != it["status"]:
        if data.status in CLOSED:
            raise Conflict("Closing requires an outcome. Use the close action.")
        sets["status"] = data.status
        events.append(event("status_changed", actor, it["status"], data.status, data.note))
        log_event(log, "item.status_changed", item_id=str(it["_id"]), **{"from": it["status"], "to": data.status})

    if "owner_id" in sent:
        o_id, o_name = _owner(data.owner_id)
        if o_id != it["owner_id"]:
            sets.update(owner_id=o_id, owner_name=o_name)
            events.append(event("reassigned", actor, it["owner_name"], o_name, data.note))
            log_event(log, "item.reassigned", item_id=str(it["_id"]), from_owner=it["owner_name"], to_owner=o_name, reason=data.note or "manual")

    if "due_date" in sent:
        new_due = parse_date(data.due_date, "due_date") if data.due_date else None
        if new_due != it["due_date"]:
            sets["due_date"] = new_due
            f = it["due_date"].strftime("%Y-%m-%d") if it["due_date"] else None
            events.append(event("due_changed", actor, f, data.due_date or None, data.note))

    if "priority" in sent and data.priority and data.priority != it["priority"]:
        sets["priority"] = data.priority
        events.append(event("updated", actor, it["priority"], data.priority, "priority changed"))

    if events:
        sets["updated_at"] = utcnow()
        items_repo.apply(it["_id"], set_fields=sets, push_events=events)
    return get_item(item_id)


def close_item(item_id, status, outcome, actor):
    """Close an item as done/dropped. An outcome (>= 5 chars) is mandatory."""
    it = get_item(item_id)
    if it["status"] in CLOSED:
        raise Conflict("This item is already closed.")
    outcome = (outcome or "").strip()
    if len(outcome) < 5:
        raise Conflict("An outcome of at least 5 characters is required to close an item.")
    now = utcnow()
    items_repo.apply(
        it["_id"],
        set_fields={"status": status, "outcome": outcome, "closed_at": now, "updated_at": now},
        push_events=[event("closed", actor, it["status"], status, outcome)],
    )
    log_event(log, "item.closed", item_id=str(it["_id"]), status=status, outcome_chars=len(outcome))
    return get_item(item_id)


def reopen_item(item_id, note, actor):
    """Reopen a closed item; a note is required and the old outcome is kept in history."""
    it = get_item(item_id)
    if it["status"] not in CLOSED:
        raise Conflict("Only closed items can be reopened.")
    note = (note or "").strip()
    if len(note) < 3:
        raise Conflict("A note explaining why is required to reopen an item.")
    ev = event("reopened", actor, it["status"], "open", note)
    ev["previous_outcome"] = it.get("outcome")
    items_repo.apply(it["_id"], set_fields={"status": "open", "closed_at": None, "outcome": None, "updated_at": utcnow()}, push_events=[ev])
    log_event(log, "item.status_changed", item_id=str(it["_id"]), **{"from": it["status"], "to": "open"})
    return get_item(item_id)
