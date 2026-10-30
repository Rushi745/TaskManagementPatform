"""Leave Handover Mode: preview what a person owns, then reassign everything in one audited step."""
import logging

from app.errors import Conflict, NotFound, ValidationFailed
from app.logging_setup import log_event
from app.repositories import items_repo, meetings_repo, people_repo
from app.schemas.handover import HandoverExecute, HandoverPreview
from app.schemas.item import ItemUpdate
from app.schemas.meeting import MeetingCreate
from app.services import item_service, kb_service, meeting_service, people_service
from app.services.ai.handover_ai import build_brief
from app.utils import oid, parse_date, today_start, utcnow

log = logging.getLogger("app.handover")


def _urgency(item, leave_to_dt):
    """overdue / during (due before the leave ends) / after (later or undated)."""
    if item["is_overdue"]:
        return "overdue"
    if item.get("due_date") and item["due_date"] <= leave_to_dt:
        return "during"
    return "after"


def preview(data: HandoverPreview):
    """All open items the person owns, grouped by urgency, with an AI brief and suggested new owners."""
    person = people_service.get_person(data.from_person_id)
    leave_to_dt = parse_date(data.leave_to)
    items = item_service.list_items(owner_id=str(person["_id"]), status="active")
    candidates = [p for p in people_repo.list_all() if p["status"] == "active" and p["_id"] != person["_id"]]
    for i in items:
        i["urgency"] = _urgency(i, leave_to_dt)
    brief, source = build_brief(person, data.leave_from, data.leave_to, items, candidates)
    rows = []
    for i in items:
        n = brief["notes"][str(i["_id"])]
        i.update(context=n["context"], suggested_owner_id=n["owner"]["_id"] if n["owner"] else None,
                 suggested_owner_name=n["owner"]["name"] if n["owner"] else None, suggestion_reason=n["reason"])
        rows.append(i)
    order = {"overdue": 0, "during": 1, "after": 2}
    rows.sort(key=lambda i: (order[i["urgency"]], i["due_date"] is None, i["due_date"] or utcnow()))
    log_event(log, "handover.previewed", person=person["name"], item_count=len(rows), source=source)
    return {"person": {"id": person["_id"], "name": person["name"]}, "leave_from": data.leave_from, "leave_to": data.leave_to,
            "overview": brief["overview"], "risks": brief["risks"], "items": rows, "source": source,
            "people": [{"id": p["_id"], "name": p["name"], "role": p.get("role")} for p in candidates]}


def execute(data: HandoverExecute, actor="system"):
    """Reassign the chosen items, record a handover meeting, and mark the person on leave."""
    person = people_service.get_person(data.from_person_id)
    problems, plan = [], []
    for k, a in enumerate(data.assignments):
        try:
            item = item_service.get_item(a.item_id)
            target = people_service.get_person(a.to_person_id)
        except NotFound:
            problems.append({"field": f"assignments.{k}", "msg": "Unknown item or person"})
            continue
        if item["owner_id"] != person["_id"] or item["status"] not in item_service.ACTIVE:
            problems.append({"field": f"assignments.{k}", "msg": f"'{item['title']}' is not an open item of {person['name']}"})
        elif target["status"] != "active" or target["_id"] == person["_id"]:
            problems.append({"field": f"assignments.{k}", "msg": f"{target['name']} cannot take over (on leave or same person)"})
        else:
            plan.append((item, target, a.context.strip()))
    if problems:
        raise ValidationFailed(problems)

    # 1) reassign (history + item.reassigned log per item)
    for item, target, context in plan:
        item_service.update_item(item["_id"], ItemUpdate(owner_id=str(target["_id"]), note=f"Leave handover: {person['name']} → {target['name']}"), actor)
        # the knowledge travels WITH the item: the new owner sees it when they open the task
        items_repo.apply(item["_id"], push_handover={"at": utcnow(), "from_id": person["_id"], "from_name": person["name"],
                                                       "to_id": target["_id"], "to_name": target["name"], "context": context or "(no notes)",
                                                       "leave_from": data.leave_from, "leave_to": data.leave_to, "by": actor})

    # 2) handover record (shows up in the meetings list; auto-indexed into the KB when completed)
    to_people = list({t["_id"]: t for _, t, _c in plan}.values())
    title = f"Handover: {person['name']} ({data.leave_from} to {data.leave_to})"
    m = meeting_service.create_meeting(MeetingCreate(
        type="handover", title=title, date=utcnow().strftime("%Y-%m-%d"),
        participant_ids=[str(person["_id"])] + [str(t["_id"]) for t in to_people],
        from_person_id=str(person["_id"]), to_person_id=str(to_people[0]["_id"]) if len(to_people) == 1 else None,
        agenda=[f"{i['title']} → {t['name']}" for i, t, _c in plan]), actor)
    meetings_repo.update(m["_id"], {
        "summary": (data.brief.split("\n")[0] if data.brief else f"{person['name']} handed over {len(plan)} item(s) before leave.") + (f" Note: {data.note}" if data.note else ""),
        "decisions": [{"text": f"'{i['title']}' reassigned to {t['name']}", "made_by": actor} for i, t, _c in plan],
        "handover": {**m["handover"], "leave_from": data.leave_from, "leave_to": data.leave_to, "brief": data.brief,
                     "item_ids": [i["_id"] for i, _t, _c in plan]}})
    for item, _t, _c in plan:  # the item now also belongs to the handover record
        items_repo.apply(item["_id"], push_events=[item_service.event("carried_forward", actor, None, str(m["_id"]), "Included in leave handover")], push_meeting=m["_id"])
    meeting_service.change_status(m["_id"], "completed", actor)

    # 3) mark on leave
    people_repo.update(person["_id"], {"status": "on_leave", "leave": {"from": data.leave_from, "to": data.leave_to}})
    log_event(log, "handover.executed", from_person=person["name"], item_count=len(plan), by=actor,
              assignments=[{"item_id": str(i["_id"]), "to": t["name"]} for i, t, _c in plan])
    return {"meeting_id": m["_id"], "reassigned": len(plan), "person": person["name"]}
