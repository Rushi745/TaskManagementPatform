"""Rule-based fallbacks used when Gemini is unavailable. Every result is marked source='fallback'."""
import re

_ITEM_PREFIX = re.compile(r"^\s*(?:[-*]\s*)?(?:todo\b|action\s*item\b|action\b|ai\b|\[\s?\]|- \[ \])\s*[:\-]?\s*", re.I)
_DECISION = re.compile(r"\b(decided|agreed|decision|we will|going with)\b", re.I)
_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def _match_owner(line, participants):
    """Find a participant mentioned in the line (@Name, full name or unique first name)."""
    low = line.lower()
    for p in participants:
        if p["name"].lower() in low:
            return p
    firsts = {}
    for p in participants:
        firsts.setdefault(p["name"].split()[0].lower(), []).append(p)
    for first, plist in firsts.items():
        if len(plist) == 1 and re.search(rf"(@|\b){re.escape(first)}\b", low):
            return plist[0]
    return None


def recap_fallback(raw_notes, participants):
    """Regex extraction of summary, decisions and items from notes. participants: [{person_id,name}]."""
    lines = [l.strip() for l in raw_notes.splitlines() if l.strip()]
    items, decisions = [], []
    for l in lines:
        has_prefix = bool(_ITEM_PREFIX.match(l))
        owner = _match_owner(l, participants) if (has_prefix or "@" in l) else None
        if has_prefix or "@" in l:
            title = _ITEM_PREFIX.sub("", l).strip(" -:")[:200]
            if len(title) >= 3:
                d = _DATE.search(l)
                items.append({"title": title, "owner": owner["name"] if owner else None,
                              "due_date": d.group(1) if d else None, "priority": "medium",
                              "evidence": l[:200], "confidence": 0.4})
        elif _DECISION.search(l):
            decisions.append(l[:300])
    return {
        "summary": " ".join(lines[:3])[:600],
        "decisions": decisions,
        "action_items": items,
        "open_questions": [],
    }


def brief_fallback(person_name, meeting, own_items, all_items):
    """Template brief built only from stored data."""
    return {
        "headline": f"Catch-up for {person_name}: {meeting['title']}",
        "what_happened": [s.strip() for s in re.split(r"(?<=[.!?])\s+", meeting.get("summary") or "No summary recorded.") if s.strip()][:4],
        "decisions_affecting_you": [d["text"] for d in meeting.get("decisions", [])],
        "your_action_items": [f"{i['title']} (due {i['due_date'].strftime('%Y-%m-%d') if i.get('due_date') else 'no date'}, {i['status']})" for i in own_items]
        or ["You have no action items from this meeting."],
        "open_questions": [],
        "read_next": [l["title"] for l in meeting.get("kb_links", [])],
    }
