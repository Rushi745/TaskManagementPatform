"""Login with pre-generated team credentials (no sign-up).

Every person gets a username (lower-case first name) and a password. Passwords are stored only as salted
hashes. A session cookie keeps the person logged in; every page and API call except /login, /health and
static files requires it, and the logged-in person is recorded as the actor in item history."""
import logging

from flask import Blueprint, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import Config
from app.logging_setup import log_event
from app.repositories import people_repo
from app.utils import request_id

log = logging.getLogger("app.auth")
bp = Blueprint("auth", __name__)
PUBLIC = ("/login", "/health", "/static/")


def username_for(name: str) -> str:
    return name.split()[0].lower()


def default_password(username: str) -> str:
    """Pre-generated demo password: <username>@<team id>, e.g. rahul@digiplus."""
    return f"{username}@{Config.TEAM_ID}"


def ensure_credentials():
    """Give every person without credentials a username + hashed default password (idempotent)."""
    for p in people_repo.list_all():
        if not p.get("password_hash"):
            u = p.get("username") or username_for(p["name"])
            people_repo.update(p["_id"], {"username": u, "password_hash": generate_password_hash(default_password(u))})


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        team = (request.form.get("team_id") or "").strip().lower()
        user = (request.form.get("user_id") or "").strip().lower()
        pw = request.form.get("password") or ""
        person = people_repo.find_by_username(user) if team == Config.TEAM_ID else None
        if person and person.get("password_hash") and check_password_hash(person["password_hash"], pw):
            session.clear()
            session["person_id"] = str(person["_id"])
            log_event(log, "auth.login", user=user)
            return redirect(request.args.get("next") or url_for("web.dashboard"))
        log_event(log, "auth.login_failed", level=logging.WARNING, user=user, team_ok=team == Config.TEAM_ID)
        error = "Invalid team ID, user ID or password."
    return render_template("login.html", error=error, team_id=Config.TEAM_ID)


@bp.post("/logout")
def logout():
    log_event(log, "auth.logout", user=(g.get("user") or {}).get("username"))
    session.clear()
    return redirect(url_for("auth.login"))


def register_auth(app):
    app.register_blueprint(bp)

    @app.before_request
    def require_login():
        g.user = None
        pid = session.get("person_id")
        if pid:
            from bson import ObjectId

            try:
                g.user = people_repo.get(ObjectId(pid))
            except Exception:
                g.user = None
        if g.user or request.path.startswith(PUBLIC):
            return None
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "UNAUTHORIZED", "message": "Please log in.", "details": [], "request_id": request_id()}}), 401
        return redirect(url_for("auth.login", next=request.path))

    @app.context_processor
    def inject_user():
        return {"current_user": g.get("user")}
