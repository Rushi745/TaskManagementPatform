"""AI handover brief: per-item context + suggested new owner, with deterministic post-validation and a template fallback."""
import logging

from app.repositories import items_repo, meetings_repo, people_repo
from app.schemas.ai import HandoverBriefOut
from app.services.ai import prompts, with_fallback
from app.services.ai.llm_client import generate_json

log = logging.getLogger("app.ai")
MAX_AI_ITEMS = 20  # keeps the prompt small for free-tier token limits


def _load_counts():
    counts = {}
    for i in items_repo.find({"status": {"$in": ["open", "in_progress", "blocked"]}}):
        if i.get("owner_id"):
            counts[i["owner_id"]] = counts.get(i["owner_id"], 0) + 1
    return counts


def heuristic_owner(item, candidates, load):
    """Prefer someone who took part in the item's meetings, then the lightest workload."""
    meeting_people = set()
    for m in meetings_repo.get_many(item.get("meeting_ids", [])):
        meeting_people |= {p["person_id"] for p in m.get("participants", [])}
    pool = [c for c in candidates if c["_id"] in meeting_people] or candidates
    if not pool:
        return None, None
    best = min(pool, key=lambda c: (load.get(c["_id"], 0), c["name"]))
    load[best["_id"]] = load.get(best["_id"], 0) + 1  # spread items across people
    why = f"Was in {item['origin_meeting_title']}; " if best["_id"] in meeting_people else ""
    return best, f"{why}lightest workload ({load[best['_id']] - 1} open items)"


def _history_summary(item):
    ev = [h["event"] for h in item.get("history", [])]
    return ", ".join(ev[-4:]) or "none"


def _template_context(item):
    bits = [f"From {item['origin_meeting_title']}", f"status {item['status'].replace('_', ' ')}"]
    if item.get("description"):
        bits.append(item["description"])
    if item.get("outcome"):
        bits.append(f"outcome: {item['outcome']}")
    return ". ".join(bits) + "."


def build_brief(person, leave_from, leave_to, items, candidates):
    """Return (brief_dict, source). brief_dict = {overview, risks, notes:{item_id: {context, owner(person|None), reason}}}."""
    load = _load_counts()
    by_id = {str(i["_id"]): i for i in items}
    by_name = {c["name"].lower(): c for c in candidates}

    def finish(overview, risks, raw_notes):
        notes = {}
        for iid, item in by_id.items():
            raw = raw_notes.get(iid, {})
            owner = by_name.get((raw.get("suggested_owner") or "").lower())  # must be a real, active person
            reason = raw.get("suggestion_reason")
            if owner:
                load[owner["_id"]] = load.get(owner["_id"], 0) + 1
            else:
                owner, reason = heuristic_owner(item, candidates, load)
            notes[iid] = {"context": raw.get("context") or _template_context(item), "owner": owner, "reason": reason}
        return {"overview": overview, "risks": risks, "notes": notes}

    def fallback():
        overdue = sum(1 for i in items if i["is_overdue"])
        overview = f"{person['name']} is on leave {leave_from} to {leave_to} and owns {len(items)} open item(s), {overdue} already overdue."
        risks = [f"'{i['title']}' is overdue." for i in items if i["is_overdue"]][:5]
        return finish(overview, risks, {})

    def ai():
        people_txt = "\n".join(f"{c['name']} ({c.get('role') or 'team'}), {load.get(c['_id'], 0)} open items" for c in candidates)
        rows = []
        for i in list(items)[:MAX_AI_ITEMS]:
            origin = meetings_repo.get(i["origin_meeting_id"]) or {}
            decisions = "; ".join(d["text"] for d in origin.get("decisions", []))[:200] or "-"
            docs = ", ".join(l["title"] for l in i.get("kb_links", [])) or "-"
            due = i["due_date"].strftime("%Y-%m-%d") if i.get("due_date") else "no date"
            rows.append(f"{i['_id']} | {i['title']} | {due} | {i['status']} | {i['origin_meeting_title']} | {decisions} | {_history_summary(i)} | {docs}")
        prompt = prompts.HANDOVER_PROMPT.format(
            from_name=person["name"], from_role=person.get("role") or "team member", leave_from=leave_from, leave_to=leave_to,
            available_people=people_txt or "(nobody available)", items="\n".join(rows))
        out = generate_json("handover", prompt, HandoverBriefOut)
        notes = {n.item_id: n.model_dump() for n in out.items if n.item_id in by_id}  # drop invented item ids
        return finish(out.overview, out.risks, notes)

    brief, source = with_fallback("handover", ai, fallback)
    return brief, source
