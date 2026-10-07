# Design: Clinic Operations Assistant

## 1. Architecture

A clinic manager types requests into a CLI. A LangGraph loop alternates between an LLM node and a `ToolNode`; tools call a deterministic service layer over SQLite. Conversation state is checkpointed per `thread_id`.

```text
CLI ─► agent (LLM + dynamic system prompt) ─ tool_calls ─► ToolNode ─► tools ─► service ─► SQLite
        ▲   │                                                    │
        │   └─ no tool_calls ─► final answer ─► CLI              │
        └──────────── ToolMessages ◄─────────────────────────────┘
        (InMemorySaver checkpoints messages per thread_id)
```

- **Database lifecycle:** The app uses in-memory SQLite with `StaticPool` and `check_same_thread=False` (`app/db/database.py`). Schema creation and deterministic seeding (`app/db/seed.py`) happen automatically on startup.
- **Clock injection:** The clinic operates on a deterministic demo clock (`app/clock.py`, Monday 2026-10-12 09:00, Asia/Tehran). All queries, service checks, and prompt templates resolve relative dates against this injected clock.

## 2. Side-effect boundary

- **The LLM decides what to attempt:** which tool to call and with what arguments.
- **The service decides whether it is valid:** half-open interval overlap `[start, end)` against the same therapist's *scheduled* appointments (excluding the appointment being moved), working days and hours, future-only times, and appointment status.
- **Atomicity:** `ToolNode` runs parallel tool calls in threads, so check-then-write could race even in one process. In this demo, `reschedule` holds a process-level lock (`_RESCHEDULE_LOCK` in `app/domain/services.py`) around the check and the write. An automated test sends two parallel reschedules to the same slot and expects one success and one `SLOT_UNAVAILABLE`. In production the database enforces this (section 7).
- **Limit of the boundary:** it protects validity, not intent. The service cannot tell whether the model picked the right patient. Intent is guarded by tool design (IDs come only from `search_appointments`), prompt rules (look up first; ask when several patients match), and eval scenario 2. In production, add human approval on writes.

## 3. Tools, user need, and orchestration

**User need.** A clinic manager's scheduling work is lookup, then options, then change, often across therapists. Scheduling is a common agent demo, so the point is not novelty. It is a write tool whose preconditions are enforced by grounded reads and a deterministic service.

| Tool | Kind | Role |
|---|---|---|
| `search_appointments` | read | Find bookings by patient, therapist, date range, status. The only source of appointment IDs. |
| `find_available_slots` | read | List open slots (15-minute grid) for a therapist, with earliest/latest time filters. |
| `reschedule_appointment` | write | Move a scheduled appointment to a new start time. |

The reads make the write safe: the model cannot guess an ID or a time, and the write tool's description states prerequisites explicitly. Deliberately omitted: a free-form SQL tool (injection risk, unbounded actions, patient-data exposure) and create/cancel tools (a smaller surface means fewer failure modes).

**Orchestration without special-casing.** The graph is a generic agent-and-tools loop with no knowledge of any particular query. Multi-step chains and parallel lookups come from:
1. Tool descriptions that state prerequisites and expected input formats.
2. System-prompt rules (read first; issue independent lookups together).
3. Tool outputs that carry the IDs and ISO datetimes the next call needs.

Offline tests show that parallel tool calls flow through the graph correctly. Whether a real model chooses well is measured by the live eval (section 6).

## 4. Failure handling

1. **Expected failures** (not found, conflict, past time, outside hours, bad state, bad input) are caught in the tool and returned as structured data: `{"status": "error", "code", "message", "retryable", "next_step"}`. The model reads them like any other tool result.
2. **Unexpected exceptions inside a tool** become `INTERNAL_ERROR` with a generic message; details are logged server-side, and raw SQL and stack traces are never sent to the model.
3. **Timeouts:** `run_with_timeout` (10 s per tool call) bounds how long the tool waits and maps to `TOOL_TIMEOUT`. The worker thread is not forcefully killed, so a timed-out write may still complete. The write tool's timeout error therefore states the outcome is unknown and instructs the model to verify with `search_appointments` before retrying.
4. **Backstop:** `ToolNode(handle_tool_errors=handle_tool_error)` converts exceptions raised outside the tool body (for example, arguments rejected by schema validation) into the same payload shape.
5. **Model behavior:** the system prompt requires plain-language error reports, forbids claiming success after an error, and requires every ID, date, and time in an answer to come from tool output. A recursion limit (`recursion_limit=15`) stops runaway tool loops (tested).

## 5. Multi-turn context, LLM abstraction, and observability

- **Context:** `InMemorySaver` stores the full message history per `thread_id`, including `ToolMessage`s with IDs and times, so follow-ups ("what about Thursday?") are resolved by the model from history. There is no trimming, and state is in-memory for the demo.
- **Multi-provider LLM abstraction (`app/agent/llm.py`):**
  - **Dynamic model resolution:** Uses LangChain's `init_chat_model` with normalized provider prefixes (`google_genai` and `openai`). Auto-detects available credentials (`GOOGLE_API_KEY` / `GEMINI_API_KEY` vs `OPENAI_API_KEY`) when `LLM_MODEL` is not specified.
  - **Temperature calibration:** Gemini 3+ models require `temperature=1.0` by default per official guidelines to prevent degradation in complex multi-step reasoning, whereas OpenAI models default to `temperature=0.0`.
  - **Network resilience and proxy routing:** `configure_proxies()` detects standard proxy environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `SOCKS_PROXY`, `SOCKS5_PROXY`, `ALL_PROXY`). It populates both upper- and lowercase environment variables and injects proxy settings directly into underlying SDK clients (`client_args` for Google GenAI and `httpx.Client(proxy=...)` for OpenAI).
- **Observability:** `JsonLogCallback` (`app/observability.py`) emits JSON lines for each model call (latency, token usage when reported, tool choices or `no_tool_called`) and each tool call (name, arguments, latency, semantic status). Status and error codes are parsed from the returned payload, because LangChain treats a tool returning an error dict as a successful invocation.
- **Trace collection:** `InMemoryTraceCollector` captures events in memory during live evals and integration tests.

## 6. Testing and evaluation

- **Offline (`uv run pytest`, no API key, no network):**
  - *LLM unit tests (`test_llm.py`):* Provider spec normalization, credential fallback logic, proxy environment propagation, and model client proxy configuration.
  - *Service unit tests (`test_services.py`):* Interval boundaries (adjacent slots pass, overlaps conflict), self-exclusion, cancelled slot non-blocking, multi-therapist independence, working hours, past time, not found, and invalid state.
  - *Tool unit tests (`test_tools.py`):* Success and failure paths for each tool, error-payload contract compliance, timeout mapping, and timeout helper execution.
  - *Graph integration tests (`test_graph.py`, scripted fake chat model):* Parallel tool calls, same-slot race condition under the process lock, multi-turn memory per `thread_id`, recursion-limit loop guard, and observability callback extraction.
- **Live eval (`uv run python -m evals.run --runs N`):** Four scripted scenarios against a real model, reporting pass rates over N runs:
  1. *`dependent_chain_reschedule`:* Search, then find slots, then reschedule; the appointment ID and time in the answer must come from tool output.
  2. *`ambiguity_trap_shared_surname`:* Two patients share a surname; the agent must not reschedule and must ask which one.
  3. *`fully_booked_disruption`:* The agent must report no availability and invent no fake slots.
  4. *`unknown_therapist_guard`:* Querying an unknown therapist returns `THERAPIST_NOT_FOUND`; the agent reports the error gracefully without writing or hallucinating.
- **Groundedness check:** IDs and times in the answer must appear in tool outputs. It is a presence check, so it cannot catch a correct time attached to the wrong patient.
- **Not covered by the live eval:** Injected tool failures and multi-turn follow-ups are tested offline with scripted fake models. Results of the last live run are recorded in the README.

## 7. Trade-offs, limitations, production changes

**Trade-offs and known limitations**
- SQLite plus a process-level lock is simple and offline, but single-process only.
- The app runs on a fixed demo clock (Monday 2026-10-12 09:00, Asia/Tehran), so seeds and "tomorrow" are deterministic. There is no real-time mode.
- Sync CLI: simple and testable, with blocking calls and no streaming.
- Ambiguity handling for patients is prompt-based, not enforced in code. Therapist names resolve by substring and return the first match, so an ambiguous therapist name is not flagged.
- A slot returned by `find_available_slots` can be taken before `reschedule`; `SLOT_UNAVAILABLE` (retryable) is the designed outcome.
- Token usage is logged only if the provider fills `llm_output["token_usage"]` (OpenAI does; Google GenAI may omit or format differently). Tool arguments, including synthetic patient names, appear in logs.

**With more time or at production scale**
- **Database-enforced overlap:** PostgreSQL exclusion constraint on a stored `end_time` column (requires `btree_gist`): `EXCLUDE USING gist (therapist_id WITH =, tstzrange(start_time, end_time) WITH &&) WHERE (status = 'scheduled')`. Map the violation (SQLSTATE `23P01`) to `SLOT_UNAVAILABLE` and drop the process lock; no distributed lock is needed.
- **State persistence:** Durable checkpointer (Postgres or Redis) and history trimming or summarization.
- **Safety and compliance:** Authentication and per-user authorization, audit logging of writes, idempotency keys (a timed-out write may have applied), human approval via `interrupt()` for writes, redaction of patient names before model calls and in logs, and data-retention review under applicable regulations (HIPAA, GDPR).
- **Reliability:** Enforced cancellation (database statement timeouts), retry budgets, model fallback routing, timezone-aware storage, and a real clock.
- **Evaluation expansion:** Additional live scenarios (injected tool failures, multi-turn follow-ups, parallel comparisons), automated pass-rate gates in CI, and trace-based production monitoring.