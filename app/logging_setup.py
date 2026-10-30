"""Structured JSON logging: file + stdout, request id injection, secret redaction."""
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import g, has_request_context

# Attributes present on every LogRecord; anything else came from `extra=`.
_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime", "request_id", "event"}
_SECRET_KEYS = {"password", "api_key", "token", "secret", "authorization"}
_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "AIza***"),
    (re.compile(r"gsk_[0-9A-Za-z]{20,}"), "gsk_***"),
    (re.compile(r"csk-[0-9A-Za-z]{20,}"), "csk-***"),
    (re.compile(r"mongodb(\+srv)?://[^:/\s]+:[^@\s]+@"), r"mongodb\1://***:***@"),
]


def redact(text: str) -> str:
    """Mask Google API keys and Mongo URI credentials inside any string."""
    for rx, repl in _PATTERNS:
        text = rx.sub(repl, text)
    return text


class RequestIdFilter(logging.Filter):
    """Attach the current request id (or '-') to every record."""

    def filter(self, record):
        record.request_id = g.get("request_id", "-") if has_request_context() else "-"
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with extras flattened in and secrets masked."""

    def format(self, record):
        data = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "event": getattr(record, "event", None),
            "message": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in _STD:
                data[k] = "***" if k.lower() in _SECRET_KEYS else v
        if record.exc_info:
            data["stack"] = self.formatException(record.exc_info)
        return redact(json.dumps(data, default=str))


def setup_logging(cfg):
    """Configure the root logger once (idempotent)."""
    root = logging.getLogger()
    if getattr(root, "_handoff_configured", False):
        return
    os.makedirs(cfg.LOG_DIR, exist_ok=True)
    fmt, flt = JsonFormatter(), RequestIdFilter()
    handlers = [
        RotatingFileHandler(os.path.join(cfg.LOG_DIR, "app.log"), maxBytes=5_000_000, backupCount=5),
        logging.StreamHandler(sys.stdout),
    ]
    root.handlers.clear()
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(flt)
        root.addHandler(h)
    root.setLevel(cfg.LOG_LEVEL.upper())
    root._handoff_configured = True
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_event(logger, event, message="", level=logging.INFO, **fields):
    """Log a domain event: log_event(log, 'item.closed', item_id=...)."""
    logger.log(level, message or event, extra={"event": event, **fields})
