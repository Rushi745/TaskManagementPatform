"""Request id + timing + access log."""
import logging
import time
import uuid

from flask import g, request

log = logging.getLogger("app.http")


def register_middleware(app):
    @app.before_request
    def _start():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.start = time.perf_counter()

    @app.after_request
    def _finish(resp):
        resp.headers["X-Request-ID"] = g.get("request_id", "-")
        if not request.path.startswith("/static"):
            ms = round((time.perf_counter() - g.get("start", time.perf_counter())) * 1000, 1)
            log.info(
                "request",
                extra={"event": "http.request", "method": request.method, "path": request.path,
                       "status": resp.status_code, "duration_ms": ms, "ip": request.remote_addr},
            )
        return resp
