from flask import Blueprint, current_app, jsonify

from app.extensions import db_ok

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Liveness + dependency status (used by Render health check)."""
    ai = "configured" if current_app.config.get("GEMINI_API_KEY") else "missing"
    return jsonify({"status": "ok", "db": "ok" if db_ok() else "down", "ai": ai})
