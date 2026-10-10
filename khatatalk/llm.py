"""Ollama LLM wrapper with JSON mode, retries, and structured error handling."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, Optional

try:
    import ollama
except ImportError:
    ollama = None

from khatatalk.config import DEFAULT_LLM_MODEL, OLLAMA_API_KEY, OLLAMA_HOST

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Raised when Ollama cannot be reached or fails permanently."""
    pass


class InvalidJSONError(Exception):
    """Raised when the LLM repeatedly fails to return valid JSON."""
    pass


def get_ollama_client() -> Any:
    """Instantiates an Ollama client with headers if OLLAMA_API_KEY is configured."""
    if ollama is None:
        raise OllamaClientError("The 'ollama' Python library is not installed.")
    try:
        headers = {}
        if OLLAMA_API_KEY:
            headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
        return ollama.Client(host=OLLAMA_HOST, headers=headers) if headers else ollama.Client(host=OLLAMA_HOST)
    except Exception as e:
        raise OllamaClientError(f"Could not connect to Ollama at {OLLAMA_HOST}: {e}")


def clean_json_text(text: str) -> str:
    """Extracts JSON substring if the LLM wrapped it in markdown code blocks."""
    text = text.strip()
    # Strip markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Find outer curly braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()
    return text


def resolve_available_model(requested_model: str, client: Optional[Any] = None) -> str:
    """Returns requested_model if available in Ollama, or falls back to any available local model."""
    try:
        active_client = client or (get_ollama_client() if ollama else None)
        if active_client:
            models_res = active_client.list()
            model_list = []
            if isinstance(models_res, dict):
                model_list = [m.get("name", m.get("model", "")) for m in models_res.get("models", [])]
            elif hasattr(models_res, "models"):
                model_list = [getattr(m, "model", getattr(m, "name", "")) for m in models_res.models]

            if any(requested_model in m or m in requested_model for m in model_list):
                return requested_model
            if model_list:
                fallback = model_list[0]
                logger.info("Requested model '%s' not in Ollama. Automatically using available local model '%s'.", requested_model, fallback)
                return fallback
    except Exception as e:
        logger.debug("Ollama model list check skipped: %s", e)
    return requested_model


def query_json(
    prompt: str,
    system: str,
    model: Optional[str] = None,
    client: Optional[Any] = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """Queries Ollama with format='json' and temperature 0.

    Retries up to `max_retries` times on invalid JSON before raising InvalidJSONError.
    """
    requested = model or DEFAULT_LLM_MODEL
    target_model = resolve_available_model(requested, client=client)

    # If client is not injected, use default ollama Client
    active_client = client
    if active_client is None:
        active_client = get_ollama_client()

    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            # We enforce temperature 0 and json format
            response = active_client.generate(
                model=target_model,
                prompt=prompt,
                system=system,
                format="json",
                options={"temperature": 0.0},
            )

            raw_response = response.get("response", "") if isinstance(response, dict) else getattr(response, "response", "")
            cleaned = clean_json_text(raw_response)
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")

        except (json.JSONDecodeError, ValueError) as err:
            logger.warning(
                "Attempt %d/%d failed to parse LLM JSON: %s (Raw: %s)",
                attempt + 1,
                max_retries + 1,
                err,
                raw_response if "raw_response" in locals() else "",
            )
            last_error = err
        except Exception as err:
            logger.error("Ollama connection or execution error: %s", err)
            raise OllamaClientError(f"Ollama execution error: {err}") from err

    raise InvalidJSONError(
        f"Failed to obtain valid JSON from model {target_model} after {max_retries + 1} attempts. Last error: {last_error}"
    )


def query_text(
    prompt: str,
    system: str,
    model: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """Queries Ollama for plain text response (e.g. drafting reminder messages)."""
    requested = model or DEFAULT_LLM_MODEL
    target_model = resolve_available_model(requested, client=client)
    active_client = client
    if active_client is None:
        active_client = get_ollama_client()

    try:
        response = active_client.generate(
            model=target_model,
            prompt=prompt,
            system=system,
            options={"temperature": 0.2},
        )
        return (
            response.get("response", "").strip()
            if isinstance(response, dict)
            else getattr(response, "response", "").strip()
        )
    except Exception as err:
        raise OllamaClientError(f"Ollama text generation error: {err}") from err
