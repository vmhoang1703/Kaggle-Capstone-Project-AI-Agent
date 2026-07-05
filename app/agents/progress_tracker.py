"""Progress-tracker: fourth pipeline stage.

The actual tracking is deterministic plain Python (not LLM judgment) exposed
as two ADK tools; a thin LlmAgent wraps them so the stage still fits the
SequentialAgent pipeline and can narrate a friendly summary.

In-memory only, module-level singleton — sized for a single CLI demo
session, not a multi-user server.
"""

from google.adk.agents import LlmAgent

from app.security import InputValidationError, sanitize_input

_mastery_log: dict[str, bool] = {}


def record_progress(step: str, mastered: bool) -> dict:
    """Records whether a learning step was mastered.

    Args:
        step: Name/label of the learning step (e.g. "Step 1: ...").
        mastered: Whether the student demonstrated mastery of this step.

    Returns:
        Confirmation payload with the step and recorded status.
    """
    try:
        clean_step = sanitize_input(step)
    except InputValidationError:
        clean_step = "unlabeled step"
    _mastery_log[clean_step] = mastered
    return {"step": clean_step, "mastered": mastered}


def get_mastery_summary() -> dict:
    """Returns the mastery summary across every step recorded so far.

    Returns:
        Totals, mastered count, mastery rate, and per-step detail.
    """
    total = len(_mastery_log)
    mastered = sum(1 for is_mastered in _mastery_log.values() if is_mastered)
    return {
        "total_steps": total,
        "mastered_steps": mastered,
        "mastery_rate": (mastered / total) if total else 0.0,
        "detail": dict(_mastery_log),
    }


PROGRESS_TRACKER_INSTRUCTION = """\
You are a progress tracker. Here is the quiz for this session:

{quiz}

For EACH step in the quiz:
1. Call record_progress with the step's label and mastered=true (this demo
   assumes every step was attempted and understood — there is no real
   student answer to grade here).

Then call get_mastery_summary once and present its result to the student as
a short, encouraging closing summary of what they learned today.
"""


def build_progress_tracker_agent(model: str) -> LlmAgent:
    return LlmAgent(
        name="progress_tracker",
        model=model,
        description="Records step mastery and reports a final summary.",
        instruction=PROGRESS_TRACKER_INSTRUCTION,
        tools=[record_progress, get_mastery_summary],
        output_key="mastery_summary",
    )
