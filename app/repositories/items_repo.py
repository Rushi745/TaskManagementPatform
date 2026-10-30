"""action_items collection access."""
from app.extensions import get_db


def _c():
    return get_db().action_items


def find(query):
    return list(_c().find(query))


def get(item_id):
    return _c().find_one({"_id": item_id})


def insert(doc):
    return _c().insert_one(doc).inserted_id


def apply(item_id, set_fields=None, push_events=None, push_meeting=None, push_handover=None):
    """Atomically $set fields, append history events and/or a meeting id."""
    update = {}
    if set_fields:
        update["$set"] = set_fields
    push = {}
    if push_events:
        push["history"] = {"$each": push_events}
    if push_meeting is not None:
        push["meeting_ids"] = push_meeting
    if push_handover is not None:
        push["handover_notes"] = push_handover
    if push:
        update["$push"] = push
    _c().update_one({"_id": item_id}, update)
