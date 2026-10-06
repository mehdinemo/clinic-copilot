"""Timeout helper for tool execution."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def run_with_timeout(
    fn: Callable[..., T],
    timeout_seconds: float,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute a callable with a timeout using a worker thread.

    Raises TimeoutError if execution exceeds timeout_seconds.
    Documented limitation: The underlying thread is not forcefully killed on timeout.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        raise TimeoutError(f"Operation timed out after {timeout_seconds}s.") from exc
    finally:
        executor.shutdown(wait=False)
