"""AI package. All LLM access goes through llm_client.generate_json."""
import logging

from app.logging_setup import log_event

log = logging.getLogger("app.ai")


def with_fallback(operation, ai_fn, fallback_fn):
    """Run ai_fn(); on ANY failure log `ai.call outcome=fallback` and run fallback_fn().
    Returns (result, source) where source is 'ai' or 'fallback'."""
    try:
        return ai_fn(), "ai"
    except Exception as e:  # AIError, post-validation bugs, SDK surprises: the user must still get a result
        log_event(log, "ai.call", f"{operation} fell back to rule-based output", level=logging.WARNING,
                  operation=operation, outcome="fallback", error_type=type(e).__name__)
        return fallback_fn(), "fallback"
