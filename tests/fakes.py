"""Scripted fake chat model for offline integration testing."""

from typing import Any, List, Optional

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import Field


class ScriptedFakeChatModel(GenericFakeChatModel):
    """Scripted fake chat model that supports tool binding and tracks history for assertions."""

    received_messages: List[List[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedFakeChatModel":
        """Mock tool binding by returning self."""
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages.append(list(messages))
        return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
