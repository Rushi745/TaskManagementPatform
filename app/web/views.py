"""Server-rendered pages. Pages only render templates; data comes via /api with fetch."""
from flask import Blueprint, render_template

bp = Blueprint("web", __name__)


@bp.get("/")
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@bp.get("/meetings")
def meetings():
    return render_template("meetings/list.html", active="meetings")


@bp.get("/meetings/new")
def meeting_new():
    return render_template("meetings/new.html", active="meetings")


@bp.get("/meetings/<meeting_id>")
def meeting_detail(meeting_id):
    return render_template("meetings/detail.html", active="meetings", meeting_id=meeting_id)


@bp.get("/items")
def items():
    return render_template("items.html", active="items")


@bp.get("/people")
def people():
    return render_template("people.html", active="people")
