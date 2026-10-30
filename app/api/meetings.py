from flask import Blueprint, request

from app.api._helpers import actor, body, ok
from app.schemas.meeting import MeetingCreate, MeetingUpdate, NextMeeting, RecapApply, RecapRequest, StatusChange
from app.services import meeting_service as svc
from app.schemas.kb import BriefRequest
from app.services.ai import brief, linker, recap

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


@bp.post("/<meeting_id>/recap")
def recap_draft(meeting_id):
    """AI recap DRAFT (not saved). Falls back to rule-based extraction if the AI fails."""
    data = request.get_json(silent=True) or {}
    return ok(recap.generate_draft(meeting_id, RecapRequest.model_validate(data).raw_notes))


@bp.post("/<meeting_id>/recap/apply")
def recap_apply(meeting_id):
    return ok(svc.apply_recap(meeting_id, body(RecapApply), actor()), 201)


@bp.post("/<meeting_id>/link")
def link_meeting(meeting_id):
    return ok(linker.link_meeting(meeting_id))


@bp.post("/<meeting_id>/brief")
def catch_up_brief(meeting_id):
    d = body(BriefRequest)
    return ok(brief.generate_brief(meeting_id, d.person_id, d.mode))
