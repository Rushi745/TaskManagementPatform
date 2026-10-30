import os
import tempfile

os.environ["MONGODB_URI"] = "mongomock://test"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["LOG_DIR"] = tempfile.mkdtemp()

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import get_db  # noqa: E402


@pytest.fixture()
def client():
    app = create_app()
    db = get_db()
    for name in db.list_collection_names():
        db[name].delete_many({})
    return app.test_client()


@pytest.fixture()
def people(client):
    out = {}
    for n in ("Rahul Mehta", "Sneha Iyer", "Priya Nair"):
        out[n.split()[0]] = client.post("/api/people", json={"name": n, "email": f"{n.split()[0].lower()}@x.com"}).json["id"]
    return out
