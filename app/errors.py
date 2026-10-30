"""Domain exceptions and the single JSON error format used by the whole API."""
import logging

from flask import g, jsonify, render_template, request
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status = 400
    code = "BAD_REQUEST"

    def __init__(self, message="Bad request", details=None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFound(AppError):
    status, code = 404, "NOT_FOUND"


class ValidationFailed(AppError):
    status, code = 422, "VALIDATION_ERROR"

    def __init__(self, details, message="Invalid input"):
        super().__init__(message, details)


class Conflict(AppError):
    status, code = 409, "CONFLICT"


class AIError(AppError):
    status, code = 503, "AI_UNAVAILABLE"


def _rid():
    return getattr(g, "request_id", "-")


def _is_api():
    return request.path.startswith("/api") or request.path == "/health"


def _json_error(status, code, message, details=None):
    body = {"error": {"code": code, "message": message, "details": details or [], "request_id": _rid()}}
    return jsonify(body), status


def pydantic_details(exc: ValidationError):
    """Turn a pydantic error into [{field, msg}]."""
    return [
        {"field": ".".join(str(p) for p in e["loc"]) or "body", "msg": e["msg"].replace("Value error, ", "")}
        for e in exc.errors()
    ]


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(e):
        if e.status == 422:
            log.warning("Validation failed", extra={"event": "validation.failed", "path": request.path, "errors": e.details})
        if _is_api():
            return _json_error(e.status, e.code, e.message, e.details)
        return render_template("error.html", code=e.status, message=e.message), e.status

    @app.errorhandler(ValidationError)
    def handle_pydantic(e):
        details = pydantic_details(e)
        log.warning("Validation failed", extra={"event": "validation.failed", "path": request.path, "errors": details})
        return _json_error(422, "VALIDATION_ERROR", "Invalid input", details)

    @app.errorhandler(HTTPException)
    def handle_http(e):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "FILE_TOO_LARGE", 415: "UNSUPPORTED_FILE"}.get(e.code, "BAD_REQUEST")
        if _is_api():
            return _json_error(e.code, code, e.description)
        return render_template("error.html", code=e.code, message=e.description), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        log.error("Unhandled exception", exc_info=True, extra={"event": "error.unhandled", "path": request.path, "exc_type": type(e).__name__})
        if _is_api():
            return _json_error(500, "INTERNAL_ERROR", "Something went wrong. Quote the request id when reporting.")
        return render_template("error.html", code=500, message="Something went wrong."), 500
