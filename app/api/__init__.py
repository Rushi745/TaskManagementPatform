"""JSON API blueprints. Register new ones in `register_api`."""
from app.api import dashboard, health, items, meetings, people


def register_api(app):
    for module in (health, people, meetings, items, dashboard):
        app.register_blueprint(module.bp)
