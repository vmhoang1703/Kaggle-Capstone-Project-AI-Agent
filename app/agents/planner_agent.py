"""Planner agent: first pipeline stage.

Breaks a study topic into an ordered list of learning steps. Pure LLM
reasoning — no external tools — so its output seeds every later stage via
ADK session state (`output_key="plan"`).
"""

from google.adk.agents import LlmAgent

PLANNER_INSTRUCTION = """\
You are a curriculum planner. The student's latest message names the topic
they want to study.

Break that topic into 3-5 concrete, ordered learning steps a beginner can
follow. Each step should be a short phrase (5-10 words) naming one concept
to learn, ordered from foundational to advanced.

Output ONLY a numbered list of steps, nothing else.
"""


def build_planner_agent(model: str) -> LlmAgent:
    return LlmAgent(
        name="planner",
        model=model,
        description="Breaks a study topic into ordered learning steps.",
        instruction=PLANNER_INSTRUCTION,
        output_key="plan",
    )
