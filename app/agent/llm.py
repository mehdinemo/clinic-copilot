"""LLM initialization helper with Google GenAI support and global proxy routing."""

import logging
import os
import re
from typing import Any, Optional, Tuple

import httpx
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GOOGLE_MODEL = "gemini-3.8-flash"


def configure_proxies() -> Optional[str]:
    """Detect and inject HTTP/SOCKS5 proxy settings into the global environment and network clients.

    Checks SOCKS_PROXY, SOCKS5_PROXY, HTTPS_PROXY, HTTP_PROXY, and ALL_PROXY.
    Injects settings into os.environ (both uppercase and lowercase) so that httpx,
    requests, urllib, and SDK network transports route traffic through the proxy.

    Returns:
        The active proxy URL string, or None if no proxy is configured.
    """
    raw_proxy = (
        os.environ.get("SOCKS_PROXY")
        or os.environ.get("SOCKS5_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
    )
    if not raw_proxy or not raw_proxy.strip():
        return None

    proxy_url = raw_proxy.strip()

    # Synchronize all standard proxy environment variables
    proxy_keys = [
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
    ]
    for key in proxy_keys:
        os.environ[key] = proxy_url

    # Sanitize password in logs if present
    sanitized = re.sub(r"://([^:@]+):[^@]+@", r"://\1:****@", proxy_url)
    logger.info("Global proxy configured: %s", sanitized)
    return proxy_url


# Auto-configure proxies on module load
configure_proxies()


def parse_model_spec(raw_spec: str) -> Tuple[str, str]:
    """Parse raw model specification into (provider, model_name).

    Normalizes various Google GenAI and OpenAI alias forms.
    """
    raw_spec = raw_spec.strip()
    if ":" in raw_spec:
        provider, model_name = raw_spec.split(":", 1)
        provider = provider.strip().lower()
        model_name = model_name.strip()

        if provider in ("google", "google-genai", "google_genai", "gemini"):
            return "google_genai", model_name
        return provider, model_name

    # Unprefixed model name detection
    lower_spec = raw_spec.lower()
    if lower_spec.startswith("gemini"):
        return "google_genai", raw_spec
    if lower_spec.startswith(("gpt-", "o1", "o3")):
        return "openai", raw_spec

    # Disambiguate based on configured API keys
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return "google_genai", raw_spec

    return "openai", raw_spec


def resolve_model_spec(model_spec: Optional[str] = None) -> Tuple[str, str]:
    """Resolve model spec from argument, environment, or active API keys."""
    if model_spec:
        return parse_model_spec(model_spec)

    env_model = os.environ.get("LLM_MODEL")
    if env_model and env_model.strip():
        return parse_model_spec(env_model)

    # Graceful fallback based on configured credentials
    has_google_key = bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))

    if has_google_key and not has_openai_key:
        return "google_genai", DEFAULT_GOOGLE_MODEL

    if has_google_key:
        return "google_genai", DEFAULT_GOOGLE_MODEL

    return "openai", DEFAULT_OPENAI_MODEL


def get_chat_model(
    model_spec: Optional[str] = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Initialize chat model dynamically based on environment configuration or parameter.

    Accepts format 'provider:model' (e.g. 'openai:gpt-4o-mini', 'google_genai:gemini-3.8-flash').
    Automatically injects proxy routing (HTTP/SOCKS5) into underlying SDK network clients.
    """
    active_proxy = configure_proxies()
    provider, model_name = resolve_model_spec(model_spec)

    # Gemini 3.0+ models use temperature=1.0 by default per official guidelines.
    # Lower temperatures on Gemini 3+ can degrade reasoning or trigger looping behavior.
    default_temp = 1.0 if (provider == "google_genai" and model_name.startswith("gemini-3")) else 0

    model_kwargs: dict[str, Any] = {
        "temperature": default_temp,
        "timeout": 30,
        "max_retries": 2,
        **kwargs,
    }

    if provider == "google_genai":
        if active_proxy and "client_args" not in model_kwargs:
            model_kwargs["client_args"] = {"proxy": active_proxy}
    elif provider == "openai":
        if active_proxy:
            if "http_client" not in model_kwargs:
                model_kwargs["http_client"] = httpx.Client(proxy=active_proxy)
            if "http_async_client" not in model_kwargs:
                model_kwargs["http_async_client"] = httpx.AsyncClient(proxy=active_proxy)

    return init_chat_model(
        model=model_name,
        model_provider=provider,
        **model_kwargs,
    )
