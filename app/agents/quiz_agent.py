"""Quiz-gen agent: third pipeline stage.

Turns the tutor's explanations into one multiple-choice comprehension
question per step, grounded with related facts pulled through the MCP
`fetch_quiz_bank` tool.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.base_toolset import BaseToolset

QUIZ_INSTRUCTION = """\
You are a quiz writer. Here are the tutor's step-by-step explanations:

{tutor_explanations}

For EACH step:
1. Call the fetch_quiz_bank tool with the step's concept as the topic to
   pull related facts for distractor answers.
2. If the result has rate_limited=true, add one gentle "(quiz bank is
   briefly rate-limited, using general knowledge for distractors)" note for
   that step, then continue using your own knowledge.
3. If the result has ok=false (and is not rate-limited) or empty
   related_facts, silently invent plausible distractors from your own
   knowledge instead — do not mention the failure.
4. Write ONE multiple-choice question (4 options, A-D) testing understanding
   of that step, and mark which option is correct.

Output format per step:
"Step N Quiz: <question>
A) ... B) ... C) ... D) ...
Correct: <letter>"
"""


def build_quiz_agent(model: str, toolset: BaseToolset) -> LlmAgent:
    return LlmAgent(
        name="quiz_gen",
        model=model,
        description="Writes one comprehension quiz question per learning step.",
        instruction=QUIZ_INSTRUCTION,
        tools=[toolset],
        output_key="quiz",
    )
