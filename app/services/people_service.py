"""People use-cases."""
import logging

from app.errors import NotFound
from app.logging_setup import log_event
from app.repositories import people_repo
from app.schemas.person import PersonCreate, PersonUpdate
from app.utils import oid, utcnow

log = logging.getLogger("app.people")


def list_people():
    """All people, sorted by name."""
    return people_repo.list_all()


def get_person(person_id):
    """Fetch one person or raise NotFound."""
    p = people_repo.get(oid(person_id, "Person"))
    if not p:
        raise NotFound("Person not found")
    return p


def create_person(data: PersonCreate):
    """Create a person; duplicate email -> Conflict."""
    doc = {"name": data.name, "email": data.email, "role": data.role, "status": "active", "leave": None, "created_at": utcnow()}
    doc["_id"] = people_repo.insert(doc)
    log_event(log, "person.created", person_id=str(doc["_id"]))
    return doc


def update_person(person_id, data: PersonUpdate):
    """Update role and/or status (returning to active clears leave dates)."""
    p = get_person(person_id)
    fields = {}
    if data.role is not None:
        fields["role"] = data.role
    if data.status is not None:
        fields["status"] = data.status
        if data.status == "active":
            fields["leave"] = None
    if fields:
        people_repo.update(p["_id"], fields)
    return get_person(person_id)
