"""CLI entrypoint — the "agent skills" capstone concept: run a full
Study Buddy session from the terminal.

Usage:
    python -m app.cli --topic "Photosynthesis"
"""

import argparse
import asyncio
import sys

from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai.errors import APIError as GeminiAPIError
from litellm.exceptions import RateLimitError as FallbackRateLimitError

from app.config import FALLBACK_MODEL, GEMINI_MODEL, get_api_key, get_fallback_api_key
from app.orchestrator import build_study_buddy_pipeline
from app.security import InputValidationError, sanitize_input

APP_NAME = "study-buddy-agent"
DEBUG_USER_ID = "debug_user_id"
FALLBACK_RATE_LIMIT_RETRIES = 2
FALLBACK_RATE_LIMIT_BACKOFF_SECONDS = 20
FALLBACK_STAGE_THROTTLE_SECONDS = 20

STATE_SECTIONS = [
    ("plan", "Learning Plan"),
    ("tutor_explanations", "Tutor"),
    ("quiz", "Quiz"),
    ("mastery_summary", "Mastery Summary"),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Study Buddy Agent — multi-agent tutor CLI"
    )
    parser.add_argument(
        "--topic", required=True, help="Study topic, e.g. 'Photosynthesis'"
    )
    return parser.parse_args(argv)


async def _run_once(
    topic: str, model, session_id: str, throttle_seconds: int = 0
) -> dict:
    """Runs one full session against `model`. Raises on any failure."""
    pipeline = build_study_buddy_pipeline(model=model, throttle_seconds=throttle_seconds)
    runner = InMemoryRunner(agent=pipeline, app_name=APP_NAME)
    try:
        await runner.run_debug(
            topic, user_id=DEBUG_USER_ID, session_id=session_id, quiet=True
        )
        session = await runner.session_service.get_session(
            app_name=APP_NAME, user_id=DEBUG_USER_ID, session_id=session_id
        )
        return session.state if session else {}
    finally:
        await runner.close()


async def _run_fallback_with_retry(topic: str) -> dict:
    """Runs the Groq fallback, retrying on its free-tier rate limit.

    Groq's free tier caps tokens-per-minute; a multi-agent session with
    several tool calls can trip it mid-run. One or two short waits usually
    clears it, so this is worth a bounded retry rather than failing outright.
    """
    model = LiteLlm(model=FALLBACK_MODEL)
    for attempt in range(FALLBACK_RATE_LIMIT_RETRIES + 1):
        try:
            return await _run_once(
                topic,
                model,
                f"session-fallback-{attempt}",
                throttle_seconds=FALLBACK_STAGE_THROTTLE_SECONDS,
            )
        except FallbackRateLimitError:
            if attempt == FALLBACK_RATE_LIMIT_RETRIES:
                raise
            print(
                f"Groq rate limit hit; waiting {FALLBACK_RATE_LIMIT_BACKOFF_SECONDS}s "
                f"before retry {attempt + 1}/{FALLBACK_RATE_LIMIT_RETRIES}...",
                file=sys.stderr,
            )
            await asyncio.sleep(FALLBACK_RATE_LIMIT_BACKOFF_SECONDS)
    raise AssertionError("unreachable")  # loop always returns or raises


async def run_session(topic: str) -> None:
    # Validation and secret checks run before any agent or MCP call, per spec AC.
    clean_topic = sanitize_input(topic)
    get_api_key()

    print(f"\n=== Study Buddy session: {clean_topic} ===\n")

    try:
        state = await _run_once(clean_topic, GEMINI_MODEL, "session-gemini")
    except GeminiAPIError as exc:
        print(
            f"Gemini unavailable ({exc.__class__.__name__}: {exc}); "
            f"falling back to {FALLBACK_MODEL}...",
            file=sys.stderr,
        )
        get_fallback_api_key()
        state = await _run_fallback_with_retry(clean_topic)

    printed_any = False
    for key, label in STATE_SECTIONS:
        if state.get(key):
            print(f"--- {label} ---")
            print(state[key])
            print()
            printed_any = True

    if not printed_any:
        print("Session produced no output.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run_session(args.topic))
    except InputValidationError as exc:
        print(f"Invalid topic: {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 — last-resort: no raw traceback to the user
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
