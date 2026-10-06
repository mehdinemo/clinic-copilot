"""LangGraph graph construction and orchestration for the clinic assistant."""

import json
import logging
from typing import Any, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.llm import get_chat_model
from app.agent.prompts import get_system_prompt
from app.tools.appointments import reschedule_appointment, search_appointments
from app.tools.availability import find_available_slots
from app.tools.errors import map_exception_to_error

logger = logging.getLogger(__name__)


def handle_tool_error(error: Exception) -> str:
    """Sanitize and structure any unexpected tool errors before feeding back to LLM."""
    logger.exception("Unexpected error in tool execution: %s", error)
    err_dict = map_exception_to_error(error)
    return json.dumps(err_dict)


def build_graph(
    model: Optional[BaseChatModel] = None,
    checkpointer: Optional[Any] = None,
) -> CompiledStateGraph:
    """Build and compile the LangGraph agent graph.

    Nodes:
      - 'agent': Dynamically generates current system prompt with clock date and calls LLM.
      - 'tools': ToolNode with tools and graceful error handling backstop.
    """
    tools = [search_appointments, find_available_slots, reschedule_appointment]
    llm = model or get_chat_model()
    bound_llm = llm.bind_tools(tools)

    def agent_node(state: MessagesState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
        system_prompt = get_system_prompt()
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        ai_message = bound_llm.invoke(messages, config=config)
        return {"messages": [ai_message]}

    tool_node = ToolNode(tools=tools, handle_tool_errors=handle_tool_error)

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    saver = checkpointer if checkpointer is not None else InMemorySaver()
    return builder.compile(checkpointer=saver)
