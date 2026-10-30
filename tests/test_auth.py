from app import create_app
from app.auth import ensure_credentials
from app.extensions import get_db

from tests.conftest import _add_person


def _fresh():
    app = create_app()
    db = get_db()
    for name in db.list_collection_names():
        db[name].delete_many({})
    _add_person("Rahul Mehta")
    ensure_credentials()
    return app.test_client()


def test_pages_and_api_require_login():
    c = _fresh()
    assert c.get("/").status_code == 302 and "/login" in c.get("/").headers["Location"]
    assert c.get("/api/items").status_code == 401
    assert c.get("/health").status_code == 200


def test_login_success_wrong_password_and_wrong_team():
    c = _fresh()
    assert c.post("/login", data={"team_id": "digiplus", "user_id": "rahul", "password": "nope"}).status_code == 200
    assert c.post("/login", data={"team_id": "other", "user_id": "rahul", "password": "rahul@digiplus"}).status_code == 200
    assert c.get("/api/items").status_code == 401
    r = c.post("/login", data={"team_id": "DigiPlus", "user_id": "Rahul", "password": "rahul@digiplus"})
    assert r.status_code == 302 and c.get("/api/items").status_code == 200


def test_no_signup_and_no_password_hash_leak():
    c = _fresh()
    c.post("/login", data={"team_id": "digiplus", "user_id": "rahul", "password": "rahul@digiplus"})
    assert c.post("/api/people", json={"name": "Hacker", "email": "h@x.com"}).status_code == 405
    assert all("password_hash" not in p for p in c.get("/api/people").json)


def test_actor_is_logged_in_user():
    c = _fresh()
    c.post("/login", data={"team_id": "digiplus", "user_id": "rahul", "password": "rahul@digiplus"})
    m = c.post("/api/meetings", json={"title": "Sync", "date": "2026-11-03"}).json
    i = c.post("/api/items", json={"title": "Do thing", "meeting_id": m["id"]}).json
    assert i["history"][0]["by"] == "Rahul Mehta"
