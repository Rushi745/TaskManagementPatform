"""MongoDB client holder. One client per process; get_db() is the only access point."""
import logging

from pymongo import MongoClient

log = logging.getLogger("app.db")
_client = None
_db_name = "handoff"


def init_mongo(cfg):
    """Create the Mongo client. A `mongomock://` URI is accepted for local tests only."""
    global _client, _db_name
    _db_name = cfg.MONGODB_DB
    if cfg.MONGODB_URI.startswith("mongomock://"):
        import mongomock  # dev-only dependency

        _client = mongomock.MongoClient()
    else:
        _client = MongoClient(cfg.MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    """Return the application database."""
    return _client[_db_name]


def db_ok() -> bool:
    """True when the database answers a ping."""
    try:
        _client.admin.command("ping")
        return True
    except Exception:
        return False


def ensure_indexes():
    """Create indexes the app relies on (idempotent)."""
    db = get_db()
    db.people.create_index("email", unique=True)
    db.meetings.create_index([("date", -1)])
    db.meetings.create_index("status")
    db.action_items.create_index("status")
    db.action_items.create_index("owner_id")
    db.action_items.create_index("due_date")
    db.action_items.create_index("meeting_ids")
