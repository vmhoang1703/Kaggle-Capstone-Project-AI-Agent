# Study Buddy Agent

**Kaggle capstone — AI Agents: Intensive Vibe Coding Course** · Track: **Agents for Good**

## Problem

Underserved students often can't access personalized, one-on-one tutoring. Given any topic, they need it broken into a learning path, explained clearly, checked for understanding, and tracked — without a human tutor on hand.

## Solution

A 4-stage multi-agent tutor pipeline, run from the command line:

1. **Planner** — breaks the topic into 3 ordered learning steps (kept small so the pipeline's total tool-call volume fits comfortably under a free-tier fallback provider's rate limits).
2. **Tutor** — explains each step in plain language, grounded in real facts pulled live from Wikipedia via an MCP tool.
3. **Quiz-gen** — writes one multiple-choice comprehension question per step, using related facts pulled via a second MCP tool.
4. **Progress-tracker** — records mastery per step (via a deterministic Python tool, not LLM guesswork) and reports a final summary.

Each stage reads the previous stage's output from shared session state — the standard [Google ADK](https://github.com/google/adk-python) sequential-pipeline pattern (`SequentialAgent` + `output_key`).

## Architecture

```
                     ┌────────────────────────┐
 user topic  ──────▶ │   SequentialAgent       │
                     │ (study_buddy_pipeline)  │
                     └────────────────────────┘
                        │        │       │       │
                        ▼        ▼       ▼       ▼
                    Planner → Tutor → Quiz-gen → Progress
                     (LLM)   (LLM+MCP) (LLM+MCP)  Tracker
                                │         │       (LLM+tool)
                                ▼         ▼
                        ┌───────────────────────┐
                        │   MCP Server(s)       │
                        │ fetch_topic_content   │
                        │ fetch_quiz_bank       │
                        └───────────────────────┘
                                │
                                ▼
                      Wikipedia REST/Action API
```

Each MCP-consuming stage gets its own `McpToolset` (own stdio subprocess of `app/mcp_server.py`), client-side filtered (`tool_filter`) to only the one tool that stage should call, instead of one shared toolset exposing both tools to every stage.

### Capstone concepts demonstrated

| Concept | Where |
|---|---|
| Agent / Multi-agent system (ADK) | `app/agents/*.py`, `app/orchestrator.py` — real `google-adk` `LlmAgent`/`SequentialAgent` |
| MCP Server | `app/mcp_server.py` — real `mcp` SDK (`FastMCP`), stdio transport |
| Security features | `app/security.py` — input sanitization, per-tool rate limiting, secret-free error handling, no PII stored |
| Deployability | `Dockerfile` — Cloud Run-compatible container |
| Agent skills (CLI) | `app/cli.py` — `python -m app.cli --topic "..."` |

Gemini is the default model. If a session hits a Gemini API error (quota, access, retired model), the CLI automatically retries the whole session once on Groq's free API (`llama-3.3-70b-versatile`, via LiteLLM) — no manual intervention needed. Set `GROQ_API_KEY` in `.env` to enable this; it's optional if Gemini is working.

## Setup

```bash
cd study-buddy-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set GOOGLE_API_KEY to your Gemini API key
```

## Run

```bash
python -m app.cli --topic "Photosynthesis"
```

Prints the learning plan, tutor explanations, quiz, and a final mastery summary.

## Test

```bash
pytest tests -q
```

Covers the sanitizer, rate limiter, and progress tracker (the deterministic, non-LLM parts of the system — the parts that benefit from unit tests).

## Deploy (optional — not required for judging)

```bash
docker build -t study-buddy-agent .
docker run --rm -e GOOGLE_API_KEY=your-key study-buddy-agent --topic "Photosynthesis"
```

For Cloud Run: build and push the image, then `gcloud run deploy --image <image> --set-env-vars GOOGLE_API_KEY=<key>` (deployed as a job/one-shot invocation, since this is a CLI tool rather than an HTTP server).

## Security notes

- No personally identifiable information is collected or stored anywhere.
- `GOOGLE_API_KEY` is read only from `.env` (gitignored) — never logged, never committed. `.env.example` contains placeholders only.
- All MCP tool inputs (and the progress tracker's step labels) are sanitized — length-capped, control characters stripped, internal whitespace normalized — before use or before being printed to the terminal.
- MCP tool calls are rate-limited per tool, per process run (each `python -m app.cli` invocation is a fresh process with a fresh limiter) to prevent runaway/looping tool use. A rate-limit hit is surfaced distinctly from a generic fetch failure.
- If a content fetch fails or is rate-limited, the pipeline degrades gracefully (falls back to the model's own knowledge) instead of crashing.

## Limitations

- Progress tracking and rate limiting are in-memory per process — sized for a single CLI run, not a persistent multi-user service.
- `fetch_quiz_bank` uses Wikipedia's search API for related facts; distractor quality depends on topic specificity.
- The full end-to-end session and MCP-degradation acceptance criteria are verified by manually running the CLI with a real `GOOGLE_API_KEY` (see Verification in the spec) — no mocked-model automated test stands in for a live run.
