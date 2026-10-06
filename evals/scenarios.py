"""Evaluation scenario definitions."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ScenarioTurn:
    """A single turn within an evaluation scenario."""

    user_prompt: str
    expected_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    expected_phrases: List[str] = field(default_factory=list)
    forbidden_phrases: List[str] = field(default_factory=list)
    check_groundedness: bool = True


@dataclass
class EvalScenario:
    """An end-to-end evaluation scenario consisting of one or more sequential turns."""

    name: str
    description: str
    turns: List[ScenarioTurn]


SCENARIOS: List[EvalScenario] = [
    EvalScenario(
        name="dependent_chain_reschedule",
        description=(
            "Find Sara Ahmadi's appointment, check Dr. Rezaei's available slots after 2 PM "
            "tomorrow, and reschedule to the earliest slot."
        ),
        turns=[
            ScenarioTurn(
                user_prompt=(
                    "Please search for Sara Ahmadi's appointments tomorrow, check Dr. Rezaei's "
                    "availability after 2 PM tomorrow, and reschedule her appointment to the "
                    "earliest available slot."
                ),
                expected_tools=[
                    "search_appointments",
                    "find_available_slots",
                    "reschedule_appointment",
                ],
                forbidden_tools=[],
                expected_phrases=["Sara Ahmadi", "14:00", "rescheduled"],
                forbidden_phrases=["cannot find", "failed"],
                check_groundedness=True,
            )
        ],
    ),
    EvalScenario(
        name="ambiguity_trap_shared_surname",
        description=(
            "Querying for 'Ahmadi' without first name must identify ambiguity and ask for "
            "clarification without calling write tools."
        ),
        turns=[
            ScenarioTurn(
                user_prompt="What appointments are scheduled for Ahmadi tomorrow?",
                expected_tools=["search_appointments"],
                forbidden_tools=["reschedule_appointment"],
                expected_phrases=["Sara", "Ali"],
                forbidden_phrases=[],
                check_groundedness=True,
            )
        ],
    ),
    EvalScenario(
        name="fully_booked_disruption",
        description="Querying availability for fully booked Dr. Moradi reports no slots available.",
        turns=[
            ScenarioTurn(
                user_prompt="Find available appointment slots for Dr. Moradi tomorrow.",
                expected_tools=["find_available_slots"],
                forbidden_tools=["reschedule_appointment"],
                expected_phrases=["no", "none", "not available", "fully booked", "0"],
                forbidden_phrases=["rescheduled"],
                check_groundedness=True,
            )
        ],
    ),
    EvalScenario(
        name="unknown_therapist_guard",
        description="Querying a nonexistent therapist reports therapist not found gracefully.",
        turns=[
            ScenarioTurn(
                user_prompt="Find slots for Dr. Strange tomorrow.",
                expected_tools=["find_available_slots"],
                forbidden_tools=["reschedule_appointment"],
                expected_phrases=["not found", "Dr. Strange", "unknown"],
                forbidden_phrases=["14:00", "09:00"],
                check_groundedness=True,
            )
        ],
    ),
]
