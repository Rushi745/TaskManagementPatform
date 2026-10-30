"""kb_docs collection access."""
from app.extensions import get_db


def _c():
    return get_db().kb_docs


def list_all():
    return list(_c().find().sort("created_at", -1))


def get(doc_id):
    return _c().find_one({"_id": doc_id})


def get_many(ids):
    return list(_c().find({"_id": {"$in": ids}}))


def insert(doc):
    return _c().insert_one(doc).inserted_id


def find_by_meeting(meeting_id):
    return _c().find_one({"meeting_id": meeting_id})


def update(doc_id, fields):
    _c().update_one({"_id": doc_id}, {"$set": fields})


def count():
    return _c().count_documents({})
