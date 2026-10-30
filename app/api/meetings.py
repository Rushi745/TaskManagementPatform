from flask import Blueprint, request

from app.api._helpers import actor, body, ok
from app.schemas.meeting import MeetingCreate, MeetingUpdate, NextMeeting, StatusChange
from app.services import meeting_service as svc

bp = Blueprint("meetings_api", __name__, url_prefix="/api/meetings")


@bp.get("")
def list_meetings():
    return ok(svc.list_meetings(request.args.get("type"), request.args.get("status")))


@bp.post("")
def create_meeting():
    return ok(svc.create_meeting(body(MeetingCreate), actor()), 201)


@bp.get("/<meeting_id>")
def get_meeting(meeting_id):
    return ok(svc.get_detail(meeting_id))


@bp.patch("/<meeting_id>")
def update_meeting(meeting_id):
    return ok(svc.update_meeting(meeting_id, body(MeetingUpdate), actor()))


@bp.post("/<meeting_id>/status")
def change_status(meeting_id):
    return ok(svc.change_status(meeting_id, body(StatusChange).status, actor()))


@bp.post("/<meeting_id>/next")
def create_next(meeting_id):
    d = body(NextMeeting)
    return ok(svc.create_next(meeting_id, d.title, d.date, actor()), 201)
