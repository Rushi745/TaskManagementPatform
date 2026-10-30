"""JSON API blueprints. Register new ones in `register_api`."""
from app.api.health import bp as health_bp


def register_api(app):
    app.register_blueprint(health_bp)
