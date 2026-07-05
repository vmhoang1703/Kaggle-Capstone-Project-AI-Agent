"""CLI entrypoint — the "agent skills" capstone concept: run a full
Study Buddy session from the terminal.

Usage:
    python -m app.cli --topic "Photosynthesis"
"""

import argparse
import asyncio
import sys

from google.adk.runners import InMemoryRunner

from app.config import get_api_key
from app.orchestrator import build_study_buddy_pipeline
from app.security import InputValidationError, sanitize_input

APP_NAME = "study-buddy-agent"
DEBUG_USER_ID = "debug_user_id"
DEBUG_SESSION_ID = "debug_session_id"

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


async def run_session(topic: str) -> None:
    # Validation and secret checks run before any agent or MCP call, per spec AC.
    clean_topic = sanitize_input(topic)
    get_api_key()

    pipeline = build_study_buddy_pipeline()
    runner = InMemoryRunner(agent=pipeline, app_name=APP_NAME)
    try:
        print(f"\n=== Study Buddy session: {clean_topic} ===\n")
        await runner.run_debug(
            clean_topic,
            user_id=DEBUG_USER_ID,
            session_id=DEBUG_SESSION_ID,
            quiet=True,
        )

        session = await runner.session_service.get_session(
            app_name=APP_NAME, user_id=DEBUG_USER_ID, session_id=DEBUG_SESSION_ID
        )
        state = session.state if session else {}

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
    finally:
        await runner.close()


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
