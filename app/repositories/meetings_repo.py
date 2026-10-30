"""meetings collection access."""
from app.extensions import get_db


def _c():
    return get_db().meetings


def list_filtered(query):
    return list(_c().find(query).sort("date", -1))


def get(meeting_id):
    return _c().find_one({"_id": meeting_id})


def get_many(ids):
    return list(_c().find({"_id": {"$in": ids}}))


def insert(doc):
    return _c().insert_one(doc).inserted_id


def update(meeting_id, fields):
    _c().update_one({"_id": meeting_id}, {"$set": fields})


def find_next_of(meeting_id):
    return _c().find_one({"previous_meeting_id": meeting_id})
