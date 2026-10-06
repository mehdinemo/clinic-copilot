"""Observability callback handlers for logging tool and model executions as structured JSON."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class JsonLogCallback(BaseCallbackHandler):
    """Callback handler that emits structured JSON events for LLM decisions and tool executions."""

    def __init__(
        self,
        stream: Optional[Any] = None,
        file_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.stream = stream
        self.file_path = file_path
        self._starts: Dict[UUID, float] = {}

        if self.file_path:
            p = Path(self.file_path)
            p.parent.mkdir(parents=True, exist_ok=True)

    def _emit(self, event_data: Dict[str, Any]) -> None:
        """Serialize and write event as a single JSON line."""
        line = json.dumps(event_data)
        if self.stream:
            self.stream.write(line + "\n")
            if hasattr(self.stream, "flush"):
                self.stream.flush()

        if self.file_path:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record model invocation start time."""
        self._starts[run_id] = time.perf_counter()

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record chat model invocation start time."""
        self._starts[run_id] = time.perf_counter()

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Log chat model completion with latency, token usage, and tool call decisions."""
        self.on_chat_model_end(response, run_id=run_id, **kwargs)

    def on_chat_model_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Log chat model completion with latency, token usage, and tool call decisions."""
        start_t = self._starts.pop(run_id, None)
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2) if start_t else None

        # Extract token usage if available
        token_usage = {}
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]

        # Detect tool call decisions
        tool_calls: List[str] = []
        for generations in response.generations:
            for gen in generations:
                msg = getattr(gen, "message", None)
                if msg and hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(tc.get("name", "unknown"))

        event = {
            "event": "chat_model_end",
            "run_id": str(run_id),
            "latency_ms": latency_ms,
            "token_usage": token_usage,
            "tool_calls": tool_calls if tool_calls else "no_tool_called",
        }
        self._emit(event)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Log tool invocation start."""
        self._starts[run_id] = time.perf_counter()
        tool_name = serialized.get("name", "unknown_tool")

        event = {
            "event": "tool_start",
            "run_id": str(run_id),
            "tool_name": tool_name,
            "args": input_str,
        }
        self._emit(event)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Log tool completion, extracting semantic status and error code from payload."""
        start_t = self._starts.pop(run_id, None)
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2) if start_t else None

        # Extract semantic status from payload
        status = "ok"
        code = None

        payload = output
        if hasattr(output, "content"):
            payload = output.content

        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                pass

        if isinstance(payload, dict):
            status = payload.get("status", "ok")
            code = payload.get("code")

        event = {
            "event": "tool_end",
            "run_id": str(run_id),
            "latency_ms": latency_ms,
            "status": status,
            "code": code,
        }
        self._emit(event)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Log tool execution failure."""
        start_t = self._starts.pop(run_id, None)
        latency_ms = round((time.perf_counter() - start_t) * 1000, 2) if start_t else None

        event = {
            "event": "tool_error",
            "run_id": str(run_id),
            "latency_ms": latency_ms,
            "error": str(error),
        }
        self._emit(event)


class InMemoryTraceCollector(JsonLogCallback):
    """In-memory trace collector for evaluation suites and integration testing."""

    def __init__(self) -> None:
        super().__init__(stream=None, file_path=None)
        self.events: List[Dict[str, Any]] = []

    def _emit(self, event_data: Dict[str, Any]) -> None:
        self.events.append(event_data)
        super()._emit(event_data)
