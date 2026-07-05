"""Wires the 4-stage pipeline into one ADK SequentialAgent + MCP toolsets.

Pipeline: planner -> tutor -> quiz_gen -> progress_tracker, each stage
reading the prior stage's output from shared session state (via
`output_key`/`{state_var}` instruction templating) rather than direct
function calls — the standard ADK sequential-pipeline pattern.
"""

import asyncio
import sys
from pathlib import Path

from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from app.agents.planner_agent import build_planner_agent
from app.agents.progress_tracker import build_progress_tracker_agent
from app.agents.quiz_agent import build_quiz_agent
from app.agents.tutor_agent import build_tutor_agent
from app.config import GEMINI_MODEL

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_throttle_callback(seconds: int):
    """Sleeps before a stage runs — used to keep a rate-limited fallback
    provider's per-minute token usage spread across the session instead of
    bursting all four stages back-to-back.
    """

    async def _throttle(callback_context):
        await asyncio.sleep(seconds)
        return None

    return _throttle


def _mcp_server_connection() -> StdioConnectionParams:
    """Spawns app/mcp_server.py as a stdio subprocess for one toolset."""
    return StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
            cwd=str(PROJECT_ROOT),
        ),
        timeout=15.0,
    )


def build_study_buddy_pipeline(
    model: str = GEMINI_MODEL, throttle_seconds: int = 0
) -> SequentialAgent:
    """Builds the full Planner -> Tutor -> Quiz-gen -> Progress-tracker pipeline.

    Each MCP-consuming stage gets its own McpToolset (own subprocess),
    filtered to only the tool it needs — least-privilege tool access.

    `throttle_seconds`, when set, adds a delay before each stage after the
    first — for a rate-limited fallback provider (e.g. Groq's free tier),
    this spreads token usage across the session instead of bursting all
    four stages within the same rolling rate-limit window.
    """
    content_toolset = McpToolset(
        connection_params=_mcp_server_connection(),
        tool_filter=["fetch_topic_content"],
    )
    quiz_toolset = McpToolset(
        connection_params=_mcp_server_connection(),
        tool_filter=["fetch_quiz_bank"],
    )

    planner = build_planner_agent(model)
    tutor = build_tutor_agent(model, content_toolset)
    quiz_gen = build_quiz_agent(model, quiz_toolset)
    progress_tracker = build_progress_tracker_agent(model)

    if throttle_seconds:
        throttle = _make_throttle_callback(throttle_seconds)
        tutor.before_agent_callback = throttle
        quiz_gen.before_agent_callback = throttle
        progress_tracker.before_agent_callback = throttle

    return SequentialAgent(
        name="study_buddy_pipeline",
        description=(
            "Turns a study topic into a taught, quizzed, tracked learning session."
        ),
        sub_agents=[planner, tutor, quiz_gen, progress_tracker],
    )
