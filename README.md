# Clinic Operations Assistant (`clinic-copilot`)

A LangGraph tool-calling agent that helps a clinic manager look up appointments, find open slots, and reschedule sessions. It runs against an in-memory SQLite database of synthetic data. Built as an NLP-engineer take-home; architecture and trade-offs are in [DESIGN.md](DESIGN.md).

Requires [uv](https://docs.astral.sh/uv/) and the Python version listed in `pyproject.toml`.

## Quick start

```bash
uv sync
cp .env.example .env                    # set LLM_MODEL and the matching API key
uv run python -m app.cli                # interactive CLI (needs an API key)
uv run pytest                           # offline test suite, no API key needed
uv run python -m evals.run --runs 3     # live eval against a real model (needs an API key)
```

Lint and format check: `uv run ruff check . && uv run ruff format --check .`

## Tools

| Tool | Kind | Purpose |
|---|---|---|
| `search_appointments` | read | Find bookings by patient, therapist, date range, status. The only source of appointment IDs. |
| `find_available_slots` | read | Open slots for a therapist, with earliest/latest time filters. |
| `reschedule_appointment` | write | Move a scheduled appointment to a new start time. |

The agent decides which tools to call; a deterministic service layer decides whether the change is valid (overlaps, working hours, past times, status). See DESIGN.md for why.

## Demo clock and seeded data

The app runs on a **fixed demo clock**: Monday 2026-10-12 09:00, Asia/Tehran (`app/clock.py`). "Today" is always that date, so "tomorrow" means Tuesday 2026-10-13 and the seeded data lines up. There is no real-time mode; tests and evals can override the clock with `clock.set_now()`.

Seed data is synthetic: therapists Dr. Rezaei and Dr. Moradi, and two patients who share a surname (Sara Ahmadi and Ali Ahmadi). Dr. Moradi is fully booked tomorrow.

## Things to try

| Prompt | What it exercises |
|---|---|
| `Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest slot after 2 PM.` | Dependent chain: search, find slots, reschedule |
| `Move Ahmadi's appointment tomorrow to 2 PM.` | Ambiguity: should ask which patient and not reschedule |
| `Find open slots for Dr. Moradi tomorrow.` | Fully booked: should report no availability |
| `Compare Dr. Rezaei's and Dr. Moradi's availability tomorrow.` | Independent lookups in one turn |
| `What about Thursday?` (after an availability question) | Multi-turn follow-up |

## Example session

```text
<paste a real transcript from `uv run python -m app.cli` here, and note the model and date it was captured with>
```

## Observability

`JsonLogCallback` (`app/observability.py`) writes JSON lines to a stream and/or file. Event format (values illustrative):

```json
{"event": "chat_model_end", "run_id": "...", "latency_ms": 812.4, "token_usage": {}, "tool_calls": ["search_appointments"]}
{"event": "tool_start", "run_id": "...", "tool_name": "search_appointments", "args": "..."}
{"event": "tool_end", "run_id": "...", "latency_ms": 6.1, "status": "ok", "code": null}
```

- `tool_calls` is `"no_tool_called"` when the model answers without a tool.
- `status` and `code` are parsed from the tool's returned payload, so a business failure such as `SLOT_UNAVAILABLE` is logged as an error even though the tool function returned normally.
- `tool_end` carries no tool name; join it to `tool_start` on `run_id`.
- Token usage is populated only for providers that fill `llm_output["token_usage"]` (OpenAI does).
- Tool arguments, including patient names, are logged. The data here is synthetic.

## Evaluation

`uv run python -m evals.run --runs N` runs scripted conversations against a real model and reports the pass rate per scenario over N runs.

| Scenario | Pass criteria |
|---|---|
| Dependent chain | Search, then find slots, then reschedule; the ID and time in the answer appear in tool output |
| Ambiguity trap | Two patients share a surname; the agent does not reschedule and asks which one |
| Fully booked therapist | The agent reports no availability and invents no slots |

The groundedness check is a presence check (IDs and times in the answer must appear in tool output). It cannot catch a correct time attached to the wrong patient. The eval does not yet cover injected tool failures or follow-up turns; those are tested offline with a scripted model.

**Last live run:** `<date, model, --runs N, pass rate per scenario>`

## Configuration

| Variable | Description | Default |
|---|---|---|
| `LLM_MODEL` | `provider:model` string for `init_chat_model` | `openai:gpt-4o-mini` |
| `OPENAI_API_KEY` | Required for OpenAI models, the CLI, and evals | none |
| `ANTHROPIC_API_KEY` | Required if `LLM_MODEL` selects an Anthropic model | none |
| `DATABASE_URL` | SQLite URL | `sqlite:///:memory:` |

## Project layout

```text
app/
├── clock.py            # fixed demo clock, CLINIC_TZ, ISO/naive conversions
├── cli.py              # REPL and run_turn()
├── observability.py    # JsonLogCallback, InMemoryTraceCollector
├── agent/              # graph.py, llm.py, prompts.py
├── domain/             # models.py, errors.py, services.py (rules, lock)
├── tools/              # schemas.py, errors.py, timeout.py, appointments.py, availability.py
└── db/                 # database.py, seed.py
tests/
├── unit/               # test_services.py, test_tools.py
├── integration/        # test_graph.py
├── conftest.py
└── fakes.py            # scripted fake chat model
evals/                  # scenarios.py, checks.py, run.py
DESIGN.md
```

## Testing

`uv run pytest` runs offline, with no network and no API key.

- **Service unit tests:** interval boundaries (adjacent slots pass, overlaps conflict), self-exclusion, cancelled appointments ignored, different therapists, working hours, past time, not found, invalid state.
- **Tool unit tests:** success and failure paths for each tool (invalid ISO input, not found, slot conflict, past time, outside hours, invalid state), the error-payload contract, timeout mapping, and the timeout helper.
- **Graph integration tests (scripted fake model):** parallel tool calls, same-slot race (one success, one `SLOT_UNAVAILABLE`), multi-turn memory per `thread_id`, recursion-limit guard, and the logging callback.

These tests verify wiring and rules, not model behavior; model behavior is what the live eval measures.

## Known limitations

- Single-process SQLite with a process-level lock; production would use a database constraint.
- Fixed demo clock; no real-time mode.
- In-memory conversation state with no history trimming.
- Patient ambiguity is handled by the prompt, not enforced in code; therapist names resolve to the first substring match.
- Tool timeouts (10 s) bound the wait but do not cancel the worker thread; a timed-out write may still apply, so the write tool's error tells the model to re-check before retrying.

More detail and production changes are in [DESIGN.md](DESIGN.md).