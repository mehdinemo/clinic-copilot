# Design: Clinic Operations Assistant

## 1. Architecture

A clinic manager types requests into a CLI. A LangGraph loop alternates between an LLM node and a `ToolNode`; tools call a deterministic service layer over SQLite. Conversation state is checkpointed per `thread_id`.

```text
CLI ─► agent (LLM + system prompt) ─ tool_calls ─► ToolNode ─► tools ─► service ─► SQLite
        ▲   │                                        │
        │   └─ no tool_calls ─► final answer ─► CLI  │
        └──────────── ToolMessages ◄─────────────────┘
        (InMemorySaver checkpoints messages per thread_id)
```

## 2. Side-effect boundary

- **The LLM decides what to attempt:** which tool to call and with what arguments.
- **The service decides whether it is valid:** half-open interval overlap `[start, end)` against the same therapist's *scheduled* appointments (excluding the appointment being moved), working days and hours, future-only times, and appointment status.
- **Atomicity:** `ToolNode` runs parallel tool calls in threads, so check-then-write could race even in one process. In this demo, `reschedule` holds a process-level lock around the check and the write. A test sends two parallel reschedules to the same slot and expects one success and one `SLOT_UNAVAILABLE`. In production the database enforces this (section 7).
- **Limit of the boundary:** it protects validity, not intent. The service cannot tell whether the model picked the right patient. Intent is guarded by tool design (IDs come only from `search_appointments`), prompt rules (look up first; ask when several patients match), and eval scenario 2. In production, add human approval on writes.

## 3. Tools, user need, and orchestration

**User need.** A clinic manager's scheduling work is lookup, then options, then change, often across therapists. Scheduling is a common agent demo, so the point is not novelty. It is a write tool whose preconditions are enforced by grounded reads and a deterministic service.

| Tool | Kind | Role |
|---|---|---|
| `search_appointments` | read | Find bookings by patient, therapist, date range, status. The only source of appointment IDs. |
| `find_available_slots` | read | List open slots (15-minute grid) for a therapist, with earliest/latest time filters. |
| `reschedule_appointment` | write | Move a scheduled appointment to a new start time. |

The reads make the write safe: the model cannot guess an ID or a time, and the write tool's description says to use them first. Deliberately omitted: a free-form SQL tool (injection risk, unbounded actions, patient-data exposure) and create/cancel tools (a smaller surface means fewer failure modes).

**Orchestration without special-casing.** The graph is a generic agent-and-tools loop with no knowledge of any particular query. Multi-step chains and parallel lookups come from (a) tool descriptions that state prerequisites, (b) system-prompt rules (read first; issue independent lookups together), and (c) tool outputs that carry the IDs and ISO datetimes the next call needs. Offline tests show that parallel tool calls flow through the graph correctly. Whether a real model chooses well is measured only by the live eval (section 6).

## 4. Failure handling

1. **Expected failures** (not found, conflict, past time, outside hours, bad state, bad input) are caught in the tool and returned as data: `{"status": "error", "code", "message", "retryable", "next_step"}`. The model reads them like any other tool result.
2. **Unexpected exceptions inside a tool** become `INTERNAL_ERROR` with a generic message; details are logged server-side, and raw SQL and stack traces are never sent to the model.
3. **Timeouts:** `run_with_timeout` (10 s per tool call) bounds how long the tool waits and maps to `TOOL_TIMEOUT`. The worker thread is not killed, so a timed-out write may still complete. The write tool's timeout error therefore says the outcome is unknown and tells the model to re-check with `search_appointments` before retrying.
4. **Backstop:** `ToolNode(handle_tool_errors=...)` converts exceptions raised outside the tool body (for example, arguments rejected by schema validation) into the same payload shape.
5. **Model behavior:** the system prompt requires plain-language error reports, forbids claiming success after an error, and requires every ID, date, and time in an answer to come from tool output. A recursion limit stops runaway tool loops (tested).

## 5. Multi-turn context and observability

- **Context:** `InMemorySaver` stores the full message history per `thread_id`, including `ToolMessage`s with IDs and times, so follow-ups ("what about Thursday?") are resolved by the model from history. There is no trimming, and state is lost on restart.
- **Observability:** `JsonLogCallback` emits JSON lines for each model call (latency, token usage when the provider reports it, and which tools the model chose or `no_tool_called`) and each tool call (name, arguments, latency, status). Status and error code are parsed from the returned payload, because LangChain treats a tool that *returns* an error dict as a successful call.

## 6. Testing and evaluation

- **Offline (`uv run pytest`, no API key):** service rules (interval boundaries, self-exclusion, cancelled slots, hours, past time), tool success and failure paths with the error-payload contract, and graph integration with a scripted fake chat model (parallel calls, same-slot race, multi-turn memory, recursion limit, callback). These prove wiring and rules, not model behavior.
- **Live eval (`uv run python -m evals.run --runs N`):** three scripted scenarios against a real model, reporting pass rate over N runs.
  1. *Dependent chain:* search, then find slots, then reschedule; the ID and time in the answer must come from tool output.
  2. *Ambiguity trap:* two patients share a surname; the agent must not reschedule and must ask which one.
  3. *Fully booked therapist:* the agent must report no availability and invent no slots.
- **Groundedness check:** IDs and times in the answer must appear in tool outputs. It is a presence check, so it cannot catch a correct time attached to the wrong patient.
- **Not covered by the live eval:** injected tool failures and follow-up turns. Those are tested only with a scripted model, so real-model behavior there is unmeasured. Results of the last live run are in the README.

## 7. Trade-offs, limitations, production changes

**Trade-offs and known limitations**
- SQLite plus a process lock is simple and fully offline, but single-process only.
- The app runs on a fixed demo clock (Monday 2026-10-12 09:00, Asia/Tehran), so seeds and "tomorrow" are deterministic. There is no real-time mode.
- Sync CLI: simple and testable, with blocking calls and no streaming.
- Ambiguity handling for patients is prompt-based, not enforced in code. Therapist names resolve by substring and return the first match, so an ambiguous therapist name is not flagged.
- A slot returned by `find_available_slots` can be taken before `reschedule`; `SLOT_UNAVAILABLE` (retryable) is the designed outcome.
- Token usage is logged only if the provider fills `llm_output["token_usage"]` (OpenAI does). Tool arguments, including patient names, appear in logs; the data here is synthetic.
- The `ToolNode` backstop is not covered by an automated test.

**With more time or at production scale**
- **Database-enforced overlap:** PostgreSQL exclusion constraint on a stored `end_time` column (requires `btree_gist`): `EXCLUDE USING gist (therapist_id WITH =, tstzrange(start_time, end_time) WITH &&) WHERE (status = 'scheduled')`. Map the violation (SQLSTATE `23P01`) to `SLOT_UNAVAILABLE` and drop the process lock; no distributed lock is needed.
- **State:** durable checkpointer (Postgres or Redis) and history trimming or summarization.
- **Safety and compliance:** authentication and per-user authorization, an audit log of writes, idempotency keys (a timed-out write may have applied), human approval via `interrupt()` for writes, redaction of patient names before model calls and in logs, and a data-retention review of the model provider under the applicable rules (e.g., HIPAA, GDPR).
- **Reliability:** enforced cancellation (database statement timeouts), retry budgets, model fallback, timezone-aware storage, and a real clock.
- **Evaluation:** more scenarios (injected failures, follow-ups, parallel lookups, multiple therapists), pass-rate thresholds in CI, and trace-based monitoring.