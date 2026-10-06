"""Integration tests for LangGraph graph orchestration using scripted fake models."""

import json
from datetime import datetime
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent.graph import build_graph
from app.cli import run_turn
from app.domain.models import Appointment
from app.observability import InMemoryTraceCollector
from tests.fakes import ScriptedFakeChatModel


def test_parallel_tool_execution(seeded_session: Session) -> None:
    """Test 1 - Parallel execution: AIMessage with two tool calls routes ToolMessages back."""
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_slots_rezaei",
                    "name": "find_available_slots",
                    "args": {
                        "therapist_name": "Dr. Rezaei",
                        "start_date": "2026-10-13T09:00:00",
                        "end_date": "2026-10-13T17:00:00",
                        "duration_minutes": 45,
                    },
                },
                {
                    "id": "call_slots_moradi",
                    "name": "find_available_slots",
                    "args": {
                        "therapist_name": "Dr. Moradi",
                        "start_date": "2026-10-13T09:00:00",
                        "end_date": "2026-10-13T17:00:00",
                        "duration_minutes": 60,
                    },
                },
            ],
        ),
        AIMessage(
            content=(
                "Dr. Rezaei has availability tomorrow afternoon, but Dr. Moradi is fully booked."
            )
        ),
    ]

    fake_model = ScriptedFakeChatModel(messages=iter(messages))
    graph = build_graph(model=fake_model)

    response = run_turn(
        graph, "Compare Dr. Rezaei and Dr. Moradi availability tomorrow", "thread_p1"
    )

    # Assert model was invoked twice (turn 1: initial tool calls, turn 2: final answer)
    assert len(fake_model.received_messages) == 2
    second_call_messages = fake_model.received_messages[1]

    # Both ToolMessages must be present in the history sent to the model
    tool_messages: List[ToolMessage] = [
        m for m in second_call_messages if isinstance(m, ToolMessage)
    ]
    assert len(tool_messages) == 2

    tool_call_ids = {m.tool_call_id for m in tool_messages}
    assert "call_slots_rezaei" in tool_call_ids
    assert "call_slots_moradi" in tool_call_ids

    # Final answer reached the caller
    assert "Dr. Rezaei has availability" in response


def test_same_slot_race_condition(seeded_session: Session) -> None:
    """Test 2 - Same-slot race: Two parallel reschedules to same slot yield 1 ok and 1 conflict."""
    # Both appointments target the 14:00 open slot on Dr. Rezaei's schedule
    target_slot = "2026-10-13T14:00:00+03:30"

    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_race_1",
                    "name": "reschedule_appointment",
                    "args": {
                        "appointment_id": "apt_rezaei_01",
                        "new_start": target_slot,
                    },
                },
                {
                    "id": "call_race_2",
                    "name": "reschedule_appointment",
                    "args": {
                        "appointment_id": "apt_rezaei_03",
                        "new_start": target_slot,
                    },
                },
            ],
        ),
        AIMessage(
            content="One reschedule succeeded, while the second resulted in a slot conflict."
        ),
    ]

    fake_model = ScriptedFakeChatModel(messages=iter(messages))
    graph = build_graph(model=fake_model)

    run_turn(graph, "Move both appointments to 14:00 tomorrow", "thread_race_1")

    assert len(fake_model.received_messages) == 2
    second_call_messages = fake_model.received_messages[1]
    tool_messages = [m for m in second_call_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 2

    # Parse payloads of both returned tool messages
    payloads: List[dict] = []
    for tm in tool_messages:
        content = tm.content
        if isinstance(content, str):
            payloads.append(json.loads(content))
        else:
            payloads.append(content)

    statuses = [p.get("status") for p in payloads]
    codes = [p.get("code") for p in payloads]

    # Exactly one must succeed ("ok"), and one must fail with SLOT_UNAVAILABLE
    assert "ok" in statuses
    assert "error" in statuses
    assert "SLOT_UNAVAILABLE" in codes

    # Verify database state: exactly one appointment is at 14:00
    seeded_session.expire_all()
    appts_at_14 = (
        seeded_session.query(Appointment)
        .filter(
            Appointment.therapist_id == "th_rezaei",
            Appointment.status == "scheduled",
            Appointment.start_time == datetime(2026, 10, 13, 14, 0),
        )
        .all()
    )
    assert len(appts_at_14) == 1


def test_multi_turn_context(seeded_session: Session) -> None:
    """Test 3 - Multi-turn: Second turn with same thread_id sees history of first turn."""
    messages = [
        AIMessage(content="I found Dr. Rezaei has an open slot at 14:00."),
        AIMessage(content="Yes, I remember Dr. Rezaei has that 14:00 slot."),
        AIMessage(content="This is a fresh session with no prior history."),
    ]

    fake_model = ScriptedFakeChatModel(messages=iter(messages))
    graph = build_graph(model=fake_model)

    # Turn 1 on thread A
    resp1 = run_turn(graph, "What slots are open tomorrow?", "thread_multi_a")
    assert "14:00" in resp1

    # Turn 2 on same thread A
    resp2 = run_turn(graph, "Do you recall the slot we discussed?", "thread_multi_a")
    assert "remember" in resp2

    # Verify fake model received Turn 1 messages in Turn 2 invocation
    turn2_messages = fake_model.received_messages[1]
    user_prompts = [m.content for m in turn2_messages if isinstance(m, HumanMessage)]
    assert "What slots are open tomorrow?" in user_prompts
    assert "Do you recall the slot we discussed?" in user_prompts

    # Turn 3 on a DIFFERENT thread B
    resp3 = run_turn(graph, "What slots are open tomorrow?", "thread_multi_b")
    assert "fresh session" in resp3

    turn3_messages = fake_model.received_messages[2]
    user_prompts_b = [m.content for m in turn3_messages if isinstance(m, HumanMessage)]
    # Thread B should NOT have Alice's prior message from Turn 2
    assert "Do you recall the slot we discussed?" not in user_prompts_b


def test_loop_guard_recursion_limit(seeded_session: Session) -> None:
    """Test 4 - Loop Guard: Infinite tool calls hit recursion_limit and return graceful message."""

    def infinite_tool_calls():
        i = 0
        while True:
            i += 1
            yield AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": f"call_loop_{i}",
                        "name": "search_appointments",
                        "args": {
                            "start_date": "2026-10-13",
                            "end_date": "2026-10-14",
                        },
                    }
                ],
            )

    fake_model = ScriptedFakeChatModel(messages=infinite_tool_calls())
    graph = build_graph(model=fake_model)

    # Invoke with small recursion limit
    response = run_turn(
        graph=graph,
        text="Search appointments in an infinite loop",
        thread_id="thread_loop_guard",
        recursion_limit=4,
    )

    # Must catch GraphRecursionError and provide actionable message without crashing
    assert "allowed steps" in response
    assert "simplifying your request" in response


def test_observability_callback_tracking(seeded_session: Session) -> None:
    """Observability: JsonLogCallback extracts semantic status and codes from tool payloads."""
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_obs_search",
                    "name": "search_appointments",
                    "args": {
                        "patient_name": "Sara Ahmadi",
                        "start_date": "2026-10-12",
                        "end_date": "2026-10-15",
                    },
                }
            ],
        ),
        AIMessage(content="Found appointments for Sara Ahmadi."),
    ]

    fake_model = ScriptedFakeChatModel(messages=iter(messages))
    graph = build_graph(model=fake_model)

    collector = InMemoryTraceCollector()
    response = run_turn(
        graph=graph,
        text="Find Sara appointments",
        thread_id="thread_obs",
        callbacks=[collector],
    )

    assert "Found appointments" in response
    events = collector.events
    assert len(events) >= 2

    # Check chat model end event
    chat_events = [e for e in events if e.get("event") == "chat_model_end"]
    assert len(chat_events) >= 1
    assert "latency_ms" in chat_events[0]
    assert chat_events[0]["latency_ms"] is not None

    # Check tool end event
    tool_events = [e for e in events if e.get("event") == "tool_end"]
    assert len(tool_events) == 1
    # Verify semantic status extraction
    assert tool_events[0]["status"] == "ok"
    assert "latency_ms" in tool_events[0]
