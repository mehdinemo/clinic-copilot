# Clinic Operations Assistant (`clinic-copilot`)

A LangGraph tool-calling agent that helps a clinic manager look up appointments, find open slots, and reschedule sessions. It runs against an in-memory SQLite database of synthetic data with multi-provider LLM support (Google Gemini and OpenAI) and automatic HTTP/SOCKS5 proxy routing. Built as an NLP-engineer take-home; architecture and trade-offs are in [DESIGN.md](DESIGN.md).

User guides are available in [English (UserGuide_en.md)](UserGuide_en.md) and [Persian (UserGuide_fa.md)](UserGuide_fa.md).

Requires [uv](https://docs.astral.sh/uv/) and Python >= 3.14 (as listed in `pyproject.toml`).

## Quick start

```bash
uv sync
cp .env.example .env                    # set LLM_MODEL and the matching API key
uv run python -m app.cli                # interactive CLI (needs an API key)
uv run pytest                           # offline test suite, no API key needed
uv run python -m evals.run --runs 3     # live eval against a real model (needs an API key)
```

Run a single evaluation scenario:
```bash
uv run python -m evals.run --scenario dependent_chain_reschedule
```

Lint and format check:
```bash
uv run ruff check . && uv run ruff format --check .
```

## Tools

| Tool | Kind | Purpose |
|---|---|---|
| `search_appointments` | read | Find bookings by patient, therapist, date range, status. The only source of appointment IDs. |
| `find_available_slots` | read | Open slots (15-minute grid) for a therapist, with earliest/latest time filters. |
| `reschedule_appointment` | write | Move a scheduled appointment to a new start time. |

The agent decides which tools to call; a deterministic service layer decides whether the change is valid (overlaps, working hours, past times, status). See [DESIGN.md](DESIGN.md) for details.

## Demo clock and seeded data

The app runs on a **fixed demo clock**: Monday 2026-10-12 09:00, Asia/Tehran (`app/clock.py`). "Today" is always that date, so "tomorrow" means Tuesday 2026-10-13 and the seeded data lines up deterministically. There is no real-time mode; tests and evals can override the clock with `clock.set_now()`.

Seed data is synthetic and auto-seeded into SQLite:
- **Therapists:** Dr. Rezaei (Clinical Psychology) and Dr. Moradi (Psychiatry).
- **Patients:** Sara Ahmadi, Ali Ahmadi (shared surname for ambiguity checks), Neda Karimi, and Babak Rahimi.
- **Key booking scenarios:**
  - Dr. Moradi is fully booked tomorrow (09:00 - 17:00 back-to-back).
  - Dr. Rezaei has a mix of 45-min and 60-min sessions tomorrow, plus a cancelled appointment occupying 14:00-15:00 (which must not block open slots).
  - Past completed appointments exist to verify historical state handling.

## Things to try

| Prompt | What it exercises |
|---|---|
| `Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest slot after 2 PM.` | Dependent chain: search, find slots, reschedule |
| `Move Ahmadi's appointment tomorrow to 2 PM.` | Ambiguity: should identify multiple patients and ask for clarification |
| `Find open slots for Dr. Moradi tomorrow.` | Fully booked: should report no availability and invent no slots |
| `Find slots for Dr. Strange tomorrow.` | Unknown therapist: gracefully reports therapist not found |
| `Compare Dr. Rezaei's and Dr. Moradi's availability tomorrow.` | Independent lookups in one turn (parallel tool execution) |
| `What about Thursday?` (after an availability question) | Multi-turn conversational context |

## Example session

```text
$ uv run python -m app.cli
==================================================
   Clinic Operations Assistant - Vertical Slice   
==================================================
Clinic Clock: 2026-10-12 Monday 09:00 (Asia/Tehran)
Session Thread: 4a2b9e6f1c7d4289b88931a72d4e5f10
Available tools: search_appointments, find_available_slots, reschedule_appointment
Type 'exit' or 'quit' to terminate.

Manager > Move Sara Ahmadi's appointment with Dr. Rezaei tomorrow to the earliest slot after 2 PM.

Assistant > Sara Ahmadi's appointment with Dr. Rezaei tomorrow (Tuesday, October 13, 2026) has been successfully rescheduled from 09:00 to the earliest available slot after 2:00 PM:
* Appointment ID: apt_rezaei_01
* Therapist: Dr. Rezaei
* Patient: Sara Ahmadi
* Old Time: 2026-10-13 09:00 - 09:45 (+03:30)
* New Time: 2026-10-13 14:00 - 14:45 (+03:30)

Manager > Move Ahmadi's appointment tomorrow to 2 PM.

Assistant > I found multiple appointments matching the surname "Ahmadi" for tomorrow (October 13, 2026):
1. Ali Ahmadi with Dr. Rezaei (10:00 - 11:00)
2. Ali Ahmadi with Dr. Moradi (11:00 - 12:00)
3. Sara Ahmadi with Dr. Moradi (12:00 - 13:00)
Could you please clarify which patient and appointment you would like to reschedule?

Manager > Find open slots for Dr. Moradi tomorrow.

Assistant > I checked Dr. Moradi's schedule for tomorrow (Tuesday, October 13, 2026). Dr. Moradi is fully booked back-to-back from 09:00 to 17:00, and there are currently no available open slots.

Manager > exit
Exiting Clinic Operations Assistant. Goodbye!
```
*Captured with `google_genai:gemini-3.5-flash-lite` on 2026-10-07.*

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
- Token usage is populated only for providers that fill `llm_output["token_usage"]` (e.g., OpenAI).
- Tool arguments, including patient names, are logged. The data here is synthetic.
- `InMemoryTraceCollector` subclasses `JsonLogCallback` for offline integration tests and the live evaluation harness.

## Evaluation

`uv run python -m evals.run --runs N` runs scripted operational scenarios against a real model and reports pass rates per scenario over N iterations.

| Scenario | Pass criteria |
|---|---|
| `dependent_chain_reschedule` | Search, then find slots, then reschedule; the appointment ID and time in the answer appear in tool output |
| `ambiguity_trap_shared_surname` | Two patients share a surname; the agent does not reschedule and asks which one |
| `fully_booked_disruption` | The agent reports no availability and invents no slots |
| `unknown_therapist_guard` | Nonexistent therapist returns `THERAPIST_NOT_FOUND`; agent reports error gracefully without writes |

- **Trajectory check:** Verifies expected tools were called and forbidden tools (e.g., writes during ambiguity) were avoided.
- **Groundedness check:** A presence check ensuring all mentioned IDs (e.g., `apt_...`) and claims originated strictly from tool outputs.
- **Scenario filter:** Run specific scenarios with `--scenario <name>`.

**Last live run:** 2026-10-07, `google_genai:gemini-3.5-flash-lite`, `--runs 3`, 100% pass rate across all 4 scenarios (12/12 turns passed).

## Configuration

Environment variables configured via `.env` (copy from `.env.example`):

| Variable | Description | Default |
|---|---|---|
| `LLM_MODEL` | `provider:model` string for `init_chat_model` (e.g., `google_genai:gemini-3.5-flash-lite`, `google_genai:gemini-3.8-flash`, `openai:gpt-4o-mini`). Auto-detected if omitted. | `google_genai:gemini-3.5-flash-lite` |
| `GOOGLE_API_KEY` | Required for Google GenAI / Gemini models (Gemini Free Tier supported) | none |
| `GEMINI_API_KEY` | Alternative environment variable for Google Gemini API key | none |
| `OPENAI_API_KEY` | Required for OpenAI models | none |
| `HTTPS_PROXY` / `HTTP_PROXY` | Optional HTTP/HTTPS proxy URL (e.g., `http://127.0.0.1:8080`) | none |
| `SOCKS_PROXY` / `SOCKS5_PROXY` / `ALL_PROXY` | Optional SOCKS5 proxy URL (e.g., `socks5://127.0.0.1:2080`) | none |
| `DATABASE_URL` | SQLAlchemy SQLite URL (defaults to in-memory) | `sqlite:///:memory:` |

*Note: Global proxy settings are automatically injected into `os.environ` and configured into underlying SDK HTTP/SOCKS clients (`httpx` and Google GenAI client arguments).*

## Project layout

```text
app/
├── clock.py            # fixed demo clock, CLINIC_TZ, ISO/naive conversions
├── cli.py              # interactive REPL and run_turn()
├── observability.py    # JsonLogCallback, InMemoryTraceCollector
├── agent/              # graph.py, llm.py (dynamic provider & proxy routing), prompts.py
├── domain/             # models.py, errors.py, services.py (rules, process lock)
├── tools/              # schemas.py, errors.py, timeout.py, appointments.py, availability.py
└── db/                 # database.py (StaticPool, auto-seed), seed.py
tests/
├── unit/               # test_services.py, test_tools.py, test_llm.py
├── integration/        # test_graph.py
├── conftest.py
└── fakes.py            # scripted fake chat model
evals/                  # scenarios.py (4 scenarios), checks.py, run.py
UserGuide_en.md         # English user guide with real-world scenarios
UserGuide_fa.md         # Persian user guide with real-world scenarios
DESIGN.md               # Architecture and technical design document
README.md
```

## Testing

`uv run pytest` runs completely offline, with no network and no API key required.

- **LLM unit tests (`tests/unit/test_llm.py`):** Provider spec normalization, credential-based fallback resolution, HTTP/SOCKS5 proxy environment injection, and model client proxy configuration.
- **Service unit tests (`tests/unit/test_services.py`):** Interval boundaries (adjacent slots pass, overlaps conflict), self-exclusion, cancelled appointments ignored, different therapists, working hours, past time, not found, invalid state.
- **Tool unit tests (`tests/unit/test_tools.py`):** Success and failure paths for each tool (invalid ISO input, not found, slot conflict, past time, outside hours, invalid state), the error-payload contract, timeout mapping, and the timeout helper.
- **Graph integration tests (`tests/integration/test_graph.py`, scripted fake model):** Parallel tool calls, same-slot race (one success, one `SLOT_UNAVAILABLE`), multi-turn memory per `thread_id`, recursion-limit guard, and the logging callback.

These tests verify wiring, proxy routing, and rules, not model behavior; model behavior is what the live eval measures.

## Known limitations

- Single-process SQLite with a process-level lock; production would use a PostgreSQL exclusion constraint.
- Fixed demo clock; no real-time mode.
- In-memory conversation state with no history trimming.
- Patient ambiguity is guided by system prompt instructions, not hard-coded in Python; therapist names resolve to the first substring match.
- Tool timeouts (10 s) bound the wait but do not cancel the worker thread; a timed-out write may still apply, so the write tool's error tells the model to re-check before retrying.

More detail and production recommendations are in [DESIGN.md](DESIGN.md).