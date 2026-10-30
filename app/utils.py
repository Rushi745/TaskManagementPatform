"""Small helpers: ids, dates, serialization."""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.errors import NotFound, ValidationFailed


def utcnow() -> datetime:
    """Current UTC time (naive-safe: we store UTC everywhere)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def oid(value, what: str = "Resource") -> ObjectId:
    """Convert a string to ObjectId or raise NotFound (invalid ids are 404s)."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        raise NotFound(f"{what} not found")


def parse_date(value, field: str = "date") -> datetime:
    """Parse YYYY-MM-DD (or ISO datetime) into a UTC datetime or raise ValidationFailed."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        raise ValidationFailed([{"field": field, "msg": "Invalid date, use YYYY-MM-DD"}])


def serialize(obj):
    """Recursively make Mongo documents JSON-safe (ObjectId->str, _id->id, datetime->iso)."""
    if isinstance(obj, list):
        return [serialize(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "password_hash":
                continue  # never send credentials to the browser
            out["id" if k == "_id" else k] = serialize(v)
        return out
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def request_id() -> str:
    """Current request id, or '-' outside a request."""
    from flask import g, has_request_context

    return g.get("request_id", "-") if has_request_context() else "-"


def today_start() -> datetime:
    """Midnight (UTC) today, used for overdue / this-week computations."""
    n = utcnow()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)
