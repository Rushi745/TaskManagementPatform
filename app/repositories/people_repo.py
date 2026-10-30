"""people collection access."""
from pymongo.errors import DuplicateKeyError

from app.errors import Conflict
from app.extensions import get_db


def _c():
    return get_db().people


def list_all():
    return list(_c().find().sort("name", 1))


def get(person_id):
    return _c().find_one({"_id": person_id})


def get_many(ids):
    return list(_c().find({"_id": {"$in": ids}}))


def find_by_username(username):
    return _c().find_one({"username": username})


def count():
    return _c().count_documents({})


def insert(doc):
    try:
        return _c().insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise Conflict("A person with this email already exists")


def update(person_id, fields):
    _c().update_one({"_id": person_id}, {"$set": fields})
