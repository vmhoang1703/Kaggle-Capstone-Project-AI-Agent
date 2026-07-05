import pytest

from app.security import InputValidationError, RateLimiter, sanitize_input


def test_sanitize_input_happy_path():
    assert sanitize_input("Photosynthesis") == "Photosynthesis"


def test_sanitize_input_strips_control_chars_and_whitespace():
    assert sanitize_input("  Photo\x00synthesis  \n") == "Photosynthesis"


@pytest.mark.parametrize("bad_input", ["", "   ", None])
def test_sanitize_input_rejects_empty(bad_input):
    with pytest.raises(InputValidationError):
        sanitize_input(bad_input)


def test_sanitize_input_rejects_over_length():
    with pytest.raises(InputValidationError):
        sanitize_input("x" * 500)


def test_rate_limiter_allows_up_to_limit():
    limiter = RateLimiter(max_calls_per_minute=3)
    for _ in range(3):
        limiter.check("tool_a")  # should not raise


def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(max_calls_per_minute=2)
    limiter.check("tool_a")
    limiter.check("tool_a")
    with pytest.raises(RuntimeError):
        limiter.check("tool_a")


def test_rate_limiter_tracks_keys_independently():
    limiter = RateLimiter(max_calls_per_minute=1)
    limiter.check("tool_a")
    limiter.check("tool_b")  # different key, independent budget — should not raise
