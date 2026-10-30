from flask import Blueprint

from app.api._helpers import body, ok
from app.schemas.person import PersonUpdate
from app.services import people_service as svc

bp = Blueprint("people_api", __name__, url_prefix="/api/people")


@bp.get("")
def list_people():
    return ok(svc.list_people())


@bp.patch("/<person_id>")
def update_person(person_id):
    return ok(svc.update_person(person_id, body(PersonUpdate)))
