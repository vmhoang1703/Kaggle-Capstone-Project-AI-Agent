"""Shared guardrails for the MCP server: input sanitization + rate limiting.

Kept separate from mcp_server.py so both the server and its tests can import
these primitives without spinning up the MCP transport.
"""

import re
import time
from collections import defaultdict, deque

from app.config import MAX_TOPIC_LENGTH

# Strips control/non-printable characters; keeps normal text, punctuation, unicode letters.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Collapses any remaining whitespace run (incl. embedded \t/\n/\r, not just at the
# ends) to a single space, so multi-line/tab-injected input can't reach prompts or URLs.
_WHITESPACE_RE = re.compile(r"\s+")


class InputValidationError(ValueError):
    """Raised when tool input fails sanitization."""


class RateLimitExceeded(RuntimeError):
    """Raised when a key exceeds its per-minute call budget.

    Distinct from generic RuntimeError so callers (e.g. mcp_server.py) can
    tell a rate-limit hit apart from an unrelated failure and surface a
    specific "slow down" response instead of a generic error.
    """


def sanitize_input(text: str | None) -> str:
    """Validates and cleans free-text input before it reaches any tool/API call.

    Raises InputValidationError on non-string input, empty input, or input
    exceeding the configured length cap, so callers get one clear failure
    mode instead of a downstream API error.
    """
    if text is None or not isinstance(text, str):
        raise InputValidationError("Input must be a non-empty string.")
    cleaned = _WHITESPACE_RE.sub(" ", _CONTROL_CHARS_RE.sub("", text)).strip()
    if not cleaned:
        raise InputValidationError("Input must not be empty.")
    if len(cleaned) > MAX_TOPIC_LENGTH:
        raise InputValidationError(
            f"Input exceeds max length of {MAX_TOPIC_LENGTH} characters."
        )
    return cleaned


class RateLimiter:
    """Simple per-key token-bucket-style limiter: N calls per rolling 60s window.

    In-memory only — fine for a single-process demo/CLI. Not shared across
    processes or restarts by design (no external state to secure/manage).
    """

    def __init__(self, max_calls_per_minute: int):
        if max_calls_per_minute < 1:
            raise ValueError("max_calls_per_minute must be >= 1")
        self.max_calls_per_minute = max_calls_per_minute
        self._calls: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        """Raises RateLimitExceeded if `key` exceeded its per-minute call budget."""
        now = time.monotonic()
        window = self._calls[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.max_calls_per_minute:
            raise RateLimitExceeded(
                f"Rate limit exceeded for '{key}': "
                f"max {self.max_calls_per_minute} calls/minute."
            )
        window.append(now)
