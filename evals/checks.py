"""Evaluation checks for trajectory, groundedness, and semantic correctness."""

import json
import re
from typing import Any, Dict, List, Tuple


def check_trajectory(
    events: List[Dict[str, Any]],
    expected_tools: List[str],
    forbidden_tools: List[str],
) -> Tuple[bool, str]:
    """Verify that expected tools were called and forbidden tools were avoided."""
    called_tools = [e["tool_name"] for e in events if e.get("event") == "tool_start"]

    for expected in expected_tools:
        if expected not in called_tools:
            return False, f"Expected tool '{expected}' was not called. Called: {called_tools}"

    for forbidden in forbidden_tools:
        if forbidden in called_tools:
            return False, f"Forbidden tool '{forbidden}' was called! Called: {called_tools}"

    return True, f"Trajectory matched. Tools called: {called_tools}"


def check_groundedness(
    response_text: str,
    events: List[Dict[str, Any]],
    user_prompt: str,
) -> Tuple[bool, str]:
    """Verify that entity IDs and claims in response_text are grounded in tool outputs."""
    # Build text knowledge pool from tool outputs and user input
    knowledge_pieces = [user_prompt]
    for event in events:
        if event.get("event") in ("tool_start", "tool_end"):
            knowledge_pieces.append(json.dumps(event))

    knowledge_pool = " ".join(knowledge_pieces).lower()

    # 1. Appointment IDs check (e.g. apt_rezaei_01, apt_moradi_02)
    id_pattern = re.compile(r"\bapt_[a-zA-Z0-9_]+\b", re.IGNORECASE)
    mentioned_ids = id_pattern.findall(response_text)

    for appt_id in mentioned_ids:
        if appt_id.lower() not in knowledge_pool:
            return (
                False,
                f"Groundedness violation: Mentioned appointment ID '{appt_id}' "
                "was never returned in any tool output.",
            )

    return True, "All mentioned entity IDs are verified in tool outputs."


def check_phrases(
    response_text: str,
    expected_phrases: List[str],
    forbidden_phrases: List[str],
) -> Tuple[bool, str]:
    """Verify that expected keywords/phrases appear and forbidden phrases do not."""
    text_lower = response_text.lower()

    if expected_phrases:
        matched_any = any(p.lower() in text_lower for p in expected_phrases)
        if not matched_any:
            return (
                False,
                f"Response did not contain any of expected phrases: {expected_phrases}. "
                f"Response: '{response_text[:120]}...'",
            )

    for forbidden in forbidden_phrases:
        if forbidden.lower() in text_lower:
            return (
                False,
                f"Response contained forbidden phrase: '{forbidden}'. "
                f"Response: '{response_text[:120]}...'",
            )

    return True, "Phrase requirements satisfied."
