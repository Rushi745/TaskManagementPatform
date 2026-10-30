"""Server-rendered pages. Pages only render templates; data comes via /api with fetch."""
from flask import Blueprint, render_template

bp = Blueprint("web", __name__)


@bp.get("/")
def dashboard():
    return render_template("dashboard.html", active="dashboard")
