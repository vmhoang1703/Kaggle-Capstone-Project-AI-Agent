"""MCP server exposing study-content tools to the agent pipeline.

Runs as its own stdio process (started by the ADK orchestrator via
McpToolset/StdioConnectionParams) so it is independently testable and
swappable for a different content backend without touching agent code.

Content source: Wikipedia REST API (public, unauthenticated, no key needed).
"""

import re
from urllib.parse import quote

import requests
from mcp.server.fastmcp import FastMCP

from app.config import MCP_RATE_LIMIT_PER_MINUTE
from app.security import InputValidationError, RateLimiter, RateLimitExceeded, sanitize_input

WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
REQUEST_TIMEOUT_SECONDS = 8
_SNIPPET_TAG_RE = re.compile(r"<[^>]+>")

mcp = FastMCP("study-buddy-content")
_rate_limiter = RateLimiter(MCP_RATE_LIMIT_PER_MINUTE)


def _check_and_clean(tool_name: str, topic: str) -> tuple[str | None, dict | None]:
    """Runs the shared guardrails for a tool call.

    Returns (clean_topic, None) on success, or (None, error_payload) on
    failure. `error_payload` sets `rate_limited: True` specifically for a
    rate-limit hit, so callers can surface a distinct "slow down" message
    instead of treating it like a generic upstream failure.
    """
    try:
        _rate_limiter.check(tool_name)
    except RateLimitExceeded as exc:
        return None, {"ok": False, "rate_limited": True, "error": str(exc)}
    try:
        return sanitize_input(topic), None
    except InputValidationError as exc:
        return None, {"ok": False, "rate_limited": False, "error": str(exc)}


@mcp.tool()
def fetch_topic_content(topic: str) -> dict:
    """Fetches a plain-language summary of `topic` for the Tutor agent to explain.

    Returns a structured error payload (never raises) on invalid input,
    rate-limit, or upstream failure — callers degrade gracefully instead of
    crashing the pipeline.
    """
    clean_topic, error = _check_and_clean("fetch_topic_content", topic)
    if error is not None:
        return error

    try:
        response = requests.get(
            WIKIPEDIA_SUMMARY_URL.format(
                title=quote(clean_topic.replace(" ", "_"), safe="")
            ),
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "study-buddy-agent/1.0 (capstone project)"},
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return {"ok": False, "rate_limited": False, "error": f"content fetch failed: {exc}"}

    content_urls = data.get("content_urls") or {}
    desktop = content_urls.get("desktop") or {}
    return {
        "ok": True,
        "topic": clean_topic,
        "summary": data.get("extract", ""),
        "source_url": desktop.get("page", ""),
    }


@mcp.tool()
def fetch_quiz_bank(topic: str) -> dict:
    """Fetches related-topic facts the Quiz-gen agent can turn into questions.

    Returns raw material only (titles + short snippets) — question
    authoring stays an LLM responsibility, not this tool's.
    """
    clean_topic, error = _check_and_clean("fetch_quiz_bank", topic)
    if error is not None:
        return error

    try:
        response = requests.get(
            WIKIPEDIA_SEARCH_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": clean_topic,
                "format": "json",
                "srlimit": 5,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "study-buddy-agent/1.0 (capstone project)"},
        )
        response.raise_for_status()
        query = response.json().get("query") or {}
        results = query.get("search") or []
    except requests.RequestException as exc:
        return {"ok": False, "rate_limited": False, "error": f"quiz bank fetch failed: {exc}"}

    facts = [
        {
            "title": r.get("title", ""),
            "snippet": _SNIPPET_TAG_RE.sub("", r.get("snippet", "")),
        }
        for r in results
    ]
    return {"ok": True, "topic": clean_topic, "related_facts": facts}


if __name__ == "__main__":
    mcp.run(transport="stdio")
