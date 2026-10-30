"""Application factory."""
import logging

from flask import Flask

from app.api import register_api
from app.config import Config
from app.errors import register_error_handlers
from app.extensions import ensure_indexes, init_mongo
from app.logging_setup import setup_logging
from app.middleware import register_middleware
from app.services.ai.llm_client import providers
from app.web import register_web


def create_app():
    """Build and configure the Flask app."""
    app = Flask(__name__)
    app.config.from_object(Config)
    setup_logging(Config)
    log = logging.getLogger("app")

    init_mongo(Config)
    try:
        ensure_indexes()
    except Exception:
        log.error("Index creation failed (is MongoDB reachable?)", exc_info=True, extra={"event": "db.index_failed"})

    if Config.SEED_ON_STARTUP:
        try:
            from scripts.seed import run_seed

            run_seed()
        except Exception:
            log.error("Seeding failed", exc_info=True, extra={"event": "seed.failed"})

    register_middleware(app)
    register_error_handlers(app)
    register_api(app)
    register_web(app)
    log.info("App started", extra={"event": "app.started", "ai_providers": [p.name for p in providers()]})
    return app
