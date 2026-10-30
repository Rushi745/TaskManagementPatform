import os
import tempfile

os.environ["MONGODB_URI"] = "mongomock://test"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["LOG_DIR"] = tempfile.mkdtemp()

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import get_db  # noqa: E402


def _add_person(name, role="Engineer"):
    from app.repositories import people_repo
    from app.utils import utcnow

    return people_repo.insert({"name": name, "email": f"{name.split()[0].lower()}@x.com", "role": role,
                               "status": "active", "leave": None, "created_at": utcnow()})


@pytest.fixture()
def client():
    app = create_app()
    db = get_db()
    for name in db.list_collection_names():
        db[name].delete_many({})
    admin = _add_person("Test Admin", "Engineering Manager")
    c = app.test_client()
    with c.session_transaction() as s:
        s["person_id"] = str(admin)
    return c


@pytest.fixture()
def people(client):
    return {n.split()[0]: str(_add_person(n)) for n in ("Rahul Mehta", "Sneha Iyer", "Priya Nair")}
