from flask import Blueprint, request

from app.api._helpers import actor, body, ok
from app.schemas.item import ItemClose, ItemCreate, ItemReopen, ItemUpdate
from app.services import item_service as svc
from app.services.ai import linker

bp = Blueprint("items_api", __name__, url_prefix="/api/items")


@bp.get("")
def list_items():
    a = request.args
    return ok(svc.list_items(a.get("status"), a.get("owner_id"), a.get("overdue") == "true", a.get("meeting_id")))


@bp.post("")
def create_item():
    d = body(ItemCreate)
    return ok(svc.create_item(title=d.title, meeting_id=d.meeting_id, owner_id=d.owner_id, due_date=d.due_date,
                              priority=d.priority, description=d.description, actor=actor()), 201)


@bp.get("/<item_id>")
def get_item(item_id):
    return ok(svc.get_item(item_id))


@bp.patch("/<item_id>")
def update_item(item_id):
    return ok(svc.update_item(item_id, body(ItemUpdate), actor()))


@bp.post("/<item_id>/close")
def close_item(item_id):
    d = body(ItemClose)
    return ok(svc.close_item(item_id, d.status, d.outcome, actor()))


@bp.post("/<item_id>/reopen")
def reopen_item(item_id):
    return ok(svc.reopen_item(item_id, body(ItemReopen).note, actor()))


@bp.post("/<item_id>/link")
def link_item(item_id):
    return ok(linker.link_item(item_id))
