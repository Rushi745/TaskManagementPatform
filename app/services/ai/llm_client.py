"""Single entry point for every LLM call.

Providers are tried in AI_PROVIDER_ORDER (default groq, cerebras, gemini); only providers with an API key
are used. Groq and Cerebras speak the OpenAI chat-completions protocol (plain HTTP via httpx); Gemini uses
its SDK. Output is always validated against a Pydantic schema. One `ai.call` log line per attempt."""
import json
import logging
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Config
from app.errors import AIError
from app.logging_setup import log_event

log = logging.getLogger("app.ai")
_gemini_client = None
SYSTEM = "You are a precise assistant. Respond with a single valid JSON object only, no markdown, no commentary."


@dataclass
class Provider:
    name: str
    kind: str  # "openai" | "gemini"
    key: str
    model: str
    base_url: str = ""
    fallback_model: str = ""


def providers() -> list[Provider]:
    """Configured providers in preferred order (those without a key are skipped)."""
    known = {
        "groq": lambda: Provider("groq", "openai", Config.GROQ_API_KEY, Config.GROQ_MODEL, "https://api.groq.com/openai/v1"),
        "cerebras": lambda: Provider("cerebras", "openai", Config.CEREBRAS_API_KEY, Config.CEREBRAS_MODEL, "https://api.cerebras.ai/v1"),
        "gemini": lambda: Provider("gemini", "gemini", Config.GEMINI_API_KEY, Config.GEMINI_MODEL, fallback_model=Config.GEMINI_FALLBACK_MODEL),
    }
    order = [p.strip().lower() for p in Config.AI_PROVIDER_ORDER.split(",") if p.strip()]
    built = [known[n]() for n in order if n in known]
    return [p for p in built if p.key]


def ai_configured() -> bool:
    """True when at least one provider has a key."""
    return bool(providers())


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0]
    return t.strip()


def _call_openai(p: Provider, model: str, prompt: str, schema) -> str:
    """OpenAI-compatible chat completion in JSON-object mode (schema is described inside the prompt)."""
    body = {
        "model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"{prompt}\n\nReturn ONLY a JSON object matching this JSON schema:\n{json.dumps(schema.model_json_schema())}"}],
    }
    r = httpx.post(f"{p.base_url}/chat/completions", json=body, headers={"Authorization": f"Bearer {p.key}"},
                   timeout=Config.AI_TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def _call_gemini(p: Provider, model: str, prompt: str, schema) -> str:
    """Gemini with native JSON-schema output."""
    global _gemini_client
    from google import genai
    from google.genai import types

    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=p.key, http_options=types.HttpOptions(timeout=Config.AI_TIMEOUT_SECONDS * 1000))
    resp = _gemini_client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0.2))
    return resp.text or ""


def _call(p: Provider, attempt: int, prompt: str, schema) -> tuple[str, str]:
    """Dispatch to the provider; returns (text, model_used)."""
    if p.kind == "gemini":
        model = p.fallback_model if attempt > 1 and p.fallback_model else p.model
        return _call_gemini(p, model, prompt, schema), model
    return _call_openai(p, p.model, prompt, schema), p.model


def generate_json(operation: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Return a validated `schema` instance from the first provider that works.

    Invalid JSON / schema errors -> retry the SAME provider with the error appended to the prompt.
    Transport errors (429, timeout, 404, 5xx) -> move on to the NEXT provider immediately.
    Raises AIError if every provider fails (callers then use the rule-based fallback)."""
    chain = providers()
    if not chain:
        raise AIError("AI not configured")
    last_error = "unknown"
    for idx, p in enumerate(chain):
        is_last = idx == len(chain) - 1
        current = prompt
        for attempt in range(1, Config.AI_MAX_ATTEMPTS + 1):
            start, out_chars, model = time.perf_counter(), 0, p.model
            try:
                text, model = _call(p, attempt, current, schema)
                text = _strip_fences(text)
                out_chars = len(text)
                data = schema.model_validate_json(text)
                log_event(log, "ai.call", operation=operation, provider=p.name, model=model, attempt=attempt, outcome="success",
                          latency_ms=round((time.perf_counter() - start) * 1000), input_chars=len(prompt), output_chars=out_chars)
                return data
            except Exception as e:
                invalid_output = isinstance(e, (ValidationError, ValueError))
                last_error = f"{p.name}: {type(e).__name__}"
                if isinstance(e, httpx.HTTPStatusError):
                    last_error += f" {e.response.status_code}"
                exhausted = attempt == Config.AI_MAX_ATTEMPTS or (not invalid_output and not is_last)
                final = exhausted and is_last
                log_event(log, "ai.call", f"{operation} via {p.name} failed", level=logging.ERROR if final else logging.WARNING,
                          operation=operation, provider=p.name, model=model, attempt=attempt, outcome="failed" if final else "retry",
                          latency_ms=round((time.perf_counter() - start) * 1000), input_chars=len(prompt), output_chars=out_chars,
                          error_type=last_error.split(": ", 1)[1])
                if invalid_output:
                    current = f"{prompt}\n\nYour previous output was invalid: {str(e)[:300]}. Return valid JSON only."
                if not invalid_output and not is_last:
                    break  # try the next provider right away
                if attempt < Config.AI_MAX_ATTEMPTS:
                    time.sleep(1)
    raise AIError(f"AI call failed on all providers ({last_error})")
