"""Tiny helpers shared by API blueprints."""
from flask import jsonify, request

from app.errors import AppError
from app.utils import serialize


def body(model):
    """Parse + validate the JSON body with a pydantic model (ValidationError -> 422 via handler)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError("Malformed or missing JSON body")
    return model.model_validate(data)


def actor() -> str:
    """Who is acting (no auth: the UI sends a chosen name in X-Actor)."""
    return (request.headers.get("X-Actor") or "Anonymous").strip()[:60]


def ok(data, status=200):
    """JSON response with Mongo types serialized."""
    return jsonify(serialize(data)), status
