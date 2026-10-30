from flask import Blueprint

from app.api._helpers import ok
from app.services import dashboard_service

bp = Blueprint("dashboard_api", __name__, url_prefix="/api/dashboard")


@bp.get("")
def dashboard():
    from flask import g

    return ok(dashboard_service.get_dashboard((g.get("user") or {}).get("_id")))
