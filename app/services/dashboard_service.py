"""Dashboard numbers."""
from datetime import timedelta

from app.repositories import items_repo, meetings_repo, people_repo
from app.services import item_service
from app.utils import today_start, utcnow


def get_dashboard(user_id=None):
    """Stats, overdue list, recent meetings, people on leave, and items handed over to the current user."""
    now, today = utcnow(), today_start()
    active = [item_service.decorate(i) for i in items_repo.find({"status": {"$in": item_service.ACTIVE}})]
    overdue = sorted([i for i in active if i["is_overdue"]], key=lambda i: i["due_date"])
    week_end = today + timedelta(days=7)
    due_week = [i for i in active if i["due_date"] and today <= i["due_date"] < week_end]
    closed_week = items_repo.find({"status": {"$in": item_service.CLOSED}, "closed_at": {"$gte": now - timedelta(days=7)}})
    meetings = meetings_repo.list_filtered({})[:5]
    leave = [p for p in people_repo.list_all() if p.get("status") == "on_leave"]
    return {
        "stats": {"open": len(active), "overdue": len(overdue), "due_this_week": len(due_week), "closed_this_week": len(closed_week)},
        "overdue_items": item_service._titles(overdue[:10]),
        "recent_meetings": meetings,
        "people_on_leave": leave,
        "handed_to_me": item_service._titles([i for i in active if user_id and i.get("owner_id") == user_id and i.get("handover_notes")]),
    }
