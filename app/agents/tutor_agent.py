"""Tutor agent: second pipeline stage.

Explains each planner-produced step in plain language, grounding each
explanation with a real Wikipedia summary fetched through the MCP
`fetch_topic_content` tool (never fabricated from the model alone).
"""

from google.adk.agents import LlmAgent
from google.adk.tools.base_toolset import BaseToolset

TUTOR_INSTRUCTION = """\
You are a patient, encouraging tutor. Here is the learning plan to teach:

{plan}

For EACH step in the plan:
1. Call the fetch_topic_content tool with a short search query for that
   step's concept to ground your explanation in real facts.
2. If the result has rate_limited=true, add one gentle "(content lookup is
   briefly rate-limited, explaining from general knowledge instead)" note
   for that step, then continue using your own knowledge.
3. If the result has ok=false (and is not rate-limited) or an empty
   summary, silently explain the step from your own knowledge instead — do
   not mention the failure to the student.
4. Write a short (3-5 sentence) plain-language explanation of that step for
   a beginner, labeled "Step N: <step name>".

Output all step explanations in order, nothing else.
"""


def build_tutor_agent(model: str, toolset: BaseToolset) -> LlmAgent:
    return LlmAgent(
        name="tutor",
        model=model,
        description="Explains each learning-plan step using grounded content.",
        instruction=TUTOR_INSTRUCTION,
        tools=[toolset],
        output_key="tutor_explanations",
    )
