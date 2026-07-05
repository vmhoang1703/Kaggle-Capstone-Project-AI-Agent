"""Environment/config loading. Single source of truth for secrets access."""

import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
# Fallback provider used only if Gemini errors (quota/access/model-not-found).
# Groq: free tier, no credit card. LiteLLM-style "groq/<model>" string,
# consumed by google.adk.models.lite_llm.LiteLlm.
FALLBACK_MODEL = os.environ.get(
    "FALLBACK_MODEL", "groq/meta-llama/llama-4-scout-17b-16e-instruct"
)


def _int_env(name: str, default: str) -> int:
    """Parses an int env var, failing fast with a clear message (not a raw
    traceback) if it's malformed — consistent with get_api_key()'s contract.
    """
    raw = os.environ.get(name, default)
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer, got: {raw!r}") from None


# MCP tool guardrails (see app/security.py) — kept here so limits are
# configurable per-deployment without touching code.
MAX_TOPIC_LENGTH = _int_env("MAX_TOPIC_LENGTH", "200")
MCP_RATE_LIMIT_PER_MINUTE = _int_env("MCP_RATE_LIMIT_PER_MINUTE", "30")


def get_api_key() -> str:
    """Returns the Gemini API key or raises a clear, secret-free error.

    This is a fail-fast presence check; google-adk reads GOOGLE_API_KEY from
    the environment directly for the actual model calls, so this exists to
    surface a clear message before any agent/MCP work starts, not to thread
    the key through the call path itself.

    Never log or echo the key itself — only whether it is present.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key.strip():
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and fill in "
            "your Gemini API key before running the app."
        )
    return api_key


def get_fallback_api_key() -> str:
    """Returns the Groq API key, or raises a clear, secret-free error.

    Only checked right before a fallback attempt — Gemini is the default
    path and most runs never touch this.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key.strip():
        raise RuntimeError(
            "Gemini failed and GROQ_API_KEY is not set, so the fallback "
            "model can't run either. Add GROQ_API_KEY to .env "
            "(free key at console.groq.com)."
        )
    return api_key
