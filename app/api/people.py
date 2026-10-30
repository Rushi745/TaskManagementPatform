from flask import Blueprint

from app.api._helpers import body, ok
from app.schemas.person import PersonCreate, PersonUpdate
from app.services import people_service as svc

bp = Blueprint("people_api", __name__, url_prefix="/api/people")


@bp.get("")
def list_people():
    return ok(svc.list_people())


@bp.post("")
def create_person():
    return ok(svc.create_person(body(PersonCreate)), 201)


@bp.patch("/<person_id>")
def update_person(person_id):
    return ok(svc.update_person(person_id, body(PersonUpdate)))
