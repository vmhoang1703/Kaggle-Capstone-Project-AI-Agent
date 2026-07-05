from unittest.mock import Mock

import pytest
import requests

from app import mcp_server
from app.security import RateLimiter


@pytest.fixture(autouse=True)
def fresh_rate_limiter(monkeypatch):
    """Each test gets its own limiter so tests don't interfere with each other."""
    monkeypatch.setattr(mcp_server, "_rate_limiter", RateLimiter(max_calls_per_minute=30))


def test_fetch_topic_content_invalid_input_returns_structured_error():
    result = mcp_server.fetch_topic_content("")
    assert result == {
        "ok": False,
        "rate_limited": False,
        "error": "Input must not be empty.",
    }


def test_fetch_topic_content_network_failure_returns_structured_error(monkeypatch):
    monkeypatch.setattr(
        mcp_server.requests,
        "get",
        Mock(side_effect=requests.RequestException("boom")),
    )
    result = mcp_server.fetch_topic_content("Photosynthesis")
    assert result["ok"] is False
    assert result["rate_limited"] is False
    assert "content fetch failed" in result["error"]


def test_fetch_topic_content_success_shape(monkeypatch):
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {
        "extract": "Photosynthesis is a process.",
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Photosynthesis"}},
    }
    monkeypatch.setattr(mcp_server.requests, "get", Mock(return_value=fake_response))

    result = mcp_server.fetch_topic_content("Photosynthesis")

    assert result["ok"] is True
    assert result["summary"] == "Photosynthesis is a process."
    assert result["source_url"] == "https://en.wikipedia.org/wiki/Photosynthesis"


def test_fetch_topic_content_handles_null_nested_fields(monkeypatch):
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {"extract": "x", "content_urls": None}
    monkeypatch.setattr(mcp_server.requests, "get", Mock(return_value=fake_response))

    result = mcp_server.fetch_topic_content("Topic")

    assert result["ok"] is True
    assert result["source_url"] == ""


def test_fetch_quiz_bank_network_failure_returns_structured_error(monkeypatch):
    monkeypatch.setattr(
        mcp_server.requests,
        "get",
        Mock(side_effect=requests.RequestException("boom")),
    )
    result = mcp_server.fetch_quiz_bank("Photosynthesis")
    assert result["ok"] is False
    assert result["rate_limited"] is False
    assert "quiz bank fetch failed" in result["error"]


def test_fetch_quiz_bank_handles_null_query_field(monkeypatch):
    fake_response = Mock()
    fake_response.raise_for_status = Mock()
    fake_response.json.return_value = {"query": None}
    monkeypatch.setattr(mcp_server.requests, "get", Mock(return_value=fake_response))

    result = mcp_server.fetch_quiz_bank("Topic")

    assert result["ok"] is True
    assert result["related_facts"] == []


def test_rate_limit_hit_is_surfaced_distinctly(monkeypatch):
    monkeypatch.setattr(mcp_server, "_rate_limiter", RateLimiter(max_calls_per_minute=1))
    monkeypatch.setattr(
        mcp_server.requests,
        "get",
        Mock(side_effect=AssertionError("should not reach network on rate-limited call")),
    )

    mcp_server._rate_limiter.check("fetch_topic_content")  # consume the only slot
    result = mcp_server.fetch_topic_content("Photosynthesis")

    assert result == {
        "ok": False,
        "rate_limited": True,
        "error": (
            "Rate limit exceeded for 'fetch_topic_content': max 1 calls/minute."
        ),
    }
