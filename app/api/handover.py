from flask import Blueprint

from app.api._helpers import actor, body, ok
from app.schemas.handover import HandoverExecute, HandoverPreview
from app.services import handover_service as svc

bp = Blueprint("handover_api", __name__, url_prefix="/api/handover")


@bp.post("/preview")
def preview():
    return ok(svc.preview(body(HandoverPreview)))


@bp.post("/execute")
def execute():
    return ok(svc.execute(body(HandoverExecute), actor()), 201)
