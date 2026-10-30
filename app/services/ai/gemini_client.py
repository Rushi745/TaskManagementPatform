"""Single entry point for every Gemini call: JSON-schema output, timeout, retry, logging."""
import logging
import time

from pydantic import BaseModel, ValidationError

from app.config import Config
from app.errors import AIError
from app.logging_setup import log_event

log = logging.getLogger("app.ai")
_client = None


def _get_client():
    """Lazy-create the SDK client so the app boots without a key."""
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        _client = genai.Client(api_key=Config.GEMINI_API_KEY,
                               http_options=types.HttpOptions(timeout=Config.AI_TIMEOUT_SECONDS * 1000))
    return _client


def _strip_fences(text: str) -> str:
    """Remove ```json fences if the model added them."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0]
    return t.strip()


def generate_json(operation: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Call Gemini with JSON-schema output and return a validated `schema` instance.

    Up to AI_MAX_ATTEMPTS attempts: attempt 2 uses the fallback model and is told what was wrong
    with the previous output. One `ai.call` log line per attempt. Raises AIError when all fail.
    """
    if not Config.GEMINI_API_KEY:
        raise AIError("AI not configured")
    from google.genai import types

    models = [Config.GEMINI_MODEL, Config.GEMINI_FALLBACK_MODEL]
    last_error, current_prompt = "unknown", prompt
    for attempt in range(1, Config.AI_MAX_ATTEMPTS + 1):
        model = models[min(attempt - 1, len(models) - 1)]
        start, out_chars = time.perf_counter(), 0
        try:
            resp = _get_client().models.generate_content(
                model=model, contents=current_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json",
                                                   response_schema=schema, temperature=0.2),
            )
            text = _strip_fences(resp.text)
            out_chars = len(text)
            data = schema.model_validate_json(text)
            log_event(log, "ai.call", operation=operation, model=model, attempt=attempt, outcome="success",
                      latency_ms=round((time.perf_counter() - start) * 1000), input_chars=len(prompt), output_chars=out_chars)
            return data
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:300]}"
            final = attempt == Config.AI_MAX_ATTEMPTS
            log_event(log, "ai.call", f"{operation} attempt {attempt} failed", level=logging.ERROR if final else logging.WARNING,
                      operation=operation, model=model, attempt=attempt, outcome="failed" if final else "retry",
                      latency_ms=round((time.perf_counter() - start) * 1000), input_chars=len(prompt),
                      output_chars=out_chars, error_type=type(e).__name__)
            if isinstance(e, (ValidationError, ValueError)):
                current_prompt = f"{prompt}\n\nYour previous output was invalid: {str(e)[:300]}. Return valid JSON only."
            if not final:
                time.sleep(1)
    raise AIError(f"AI call failed after {Config.AI_MAX_ATTEMPTS} attempts: {last_error}")
