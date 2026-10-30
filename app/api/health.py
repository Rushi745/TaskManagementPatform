from flask import Blueprint, jsonify

from app.extensions import db_ok
from app.services.ai.llm_client import ai_configured, providers

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Liveness + dependency status (used by Render health check)."""
    ai = "configured" if ai_configured() else "missing"
    return jsonify({"status": "ok", "db": "ok" if db_ok() else "down", "ai": ai, "providers": [p.name for p in providers()]})
