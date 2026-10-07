"""Command-line interface (CLI) and turn runner for Clinic Operations Assistant."""

import logging
import sys
import uuid
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from app import clock
from app.agent.graph import build_graph
from app.db.database import init_and_seed_db

logger = logging.getLogger(__name__)


def _extract_message_text(content: Any) -> str:
    """Safely extract plain text from diverse message content payloads."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(content)


def run_turn(
    graph: CompiledStateGraph,
    text: str,
    thread_id: str,
    recursion_limit: int = 15,
    callbacks: Optional[List[Any]] = None,
) -> str:
    """Execute a single conversation turn against the LangGraph agent without I/O side effects."""
    config: Dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }
    if callbacks:
        config["callbacks"] = callbacks

    try:
        result = graph.invoke({"messages": [HumanMessage(content=text)]}, config=config)
        messages: List[BaseMessage] = result.get("messages", [])

        # Find the final assistant response
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                text_content = _extract_message_text(msg.content)
                if text_content.strip():
                    return text_content.strip()

        return "I completed the request, but have no further details to report."

    except GraphRecursionError:
        logger.warning("Graph recursion limit hit for thread %s", thread_id)
        return (
            "I could not complete the operation within the allowed steps. "
            "Please try simplifying your request."
        )
    except Exception as exc:
        logger.exception("Provider or runtime error in run_turn: %s", exc)
        return f"Error executing request: {exc}"


def main() -> None:
    """Initialize resources and run the interactive CLI REPL."""
    load_dotenv()
    print("==================================================")
    print("   Clinic Operations Assistant - Vertical Slice   ")
    print("==================================================")

    # 1. Initialize in-memory SQLite database, create schema, and seed deterministically
    init_and_seed_db()

    # 2. Build graph
    try:
        graph = build_graph()
    except Exception as exc:
        print(f"Failed to initialize agent graph: {exc}", file=sys.stderr)
        print("Please verify that your LLM_MODEL and provider API keys are configured in .env.")
        return

    # 3. Session thread
    session_thread_id = uuid.uuid4().hex
    current_time_str = clock.now().strftime("%Y-%m-%d %A %H:%M")
    print(f"Clinic Clock: {current_time_str} ({clock.CLINIC_TZ})")
    print(f"Session Thread: {session_thread_id}")
    print("Available tools: search_appointments, find_available_slots, reschedule_appointment")
    print("Type 'exit' or 'quit' to terminate.\n")

    while True:
        try:
            user_input = input("Manager > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting Clinic Operations Assistant. Goodbye!")
                break

            response = run_turn(graph, user_input, session_thread_id)
            print(f"\nAssistant > {response}\n")

        except KeyboardInterrupt, EOFError:
            print("\nSession interrupted. Goodbye!")
            break


if __name__ == "__main__":
    main()
