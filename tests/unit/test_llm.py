"""Unit tests for app.agent.llm (model resolution, provider normalization, proxy configuration)."""

import os
from typing import Generator

import pytest
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.agent.llm import (
    configure_proxies,
    get_chat_model,
    parse_model_spec,
    resolve_model_spec,
)


@pytest.fixture(autouse=True)
def clean_env() -> Generator[None, None, None]:
    """Clean proxy and model env vars around each test."""
    proxy_keys = [
        "HTTP_PROXY",
        "http_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "SOCKS_PROXY",
        "SOCKS5_PROXY",
        "LLM_MODEL",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
    ]
    old_vals = {k: os.environ.get(k) for k in proxy_keys}
    for k in proxy_keys:
        os.environ.pop(k, None)
    yield
    for k, v in old_vals.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


def test_parse_model_spec_providers() -> None:
    """parse_model_spec normalizes provider names and defaults."""
    assert parse_model_spec("openai:gpt-4o-mini") == ("openai", "gpt-4o-mini")
    assert parse_model_spec("google:gemini-3.8-flash") == ("google_genai", "gemini-3.8-flash")
    assert parse_model_spec("google-genai:gemini-3.8-flash") == (
        "google_genai",
        "gemini-3.8-flash",
    )
    assert parse_model_spec("google_genai:gemini-3.8-flash") == (
        "google_genai",
        "gemini-3.8-flash",
    )
    assert parse_model_spec("gemini:gemini-3.7-flash") == ("google_genai", "gemini-3.7-flash")
    assert parse_model_spec("gemini-3.8-flash") == ("google_genai", "gemini-3.8-flash")
    assert parse_model_spec("gpt-4o-mini") == ("openai", "gpt-4o-mini")


def test_resolve_model_spec_fallback() -> None:
    """resolve_model_spec falls back gracefully based on available credentials."""
    # 1. No env vars -> default openai:gpt-4o-mini
    assert resolve_model_spec() == ("openai", "gpt-4o-mini")

    # 2. Only GOOGLE_API_KEY set -> defaults to google_genai
    os.environ["GOOGLE_API_KEY"] = "fake-key"
    assert resolve_model_spec() == ("google_genai", "gemini-3.8-flash")

    # 3. LLM_MODEL explicitly set -> overrides credentials
    os.environ["LLM_MODEL"] = "google_genai:gemini-3.5-flash-lite"
    assert resolve_model_spec() == ("google_genai", "gemini-3.5-flash-lite")

    # 4. Explicit parameter -> overrides LLM_MODEL
    assert resolve_model_spec("openai:gpt-4o") == ("openai", "gpt-4o")


def test_configure_proxies_http() -> None:
    """configure_proxies propagates HTTP_PROXY to standard environment variables."""
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:8080"
    active = configure_proxies()

    assert active == "http://127.0.0.1:8080"
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:8080"
    assert os.environ["http_proxy"] == "http://127.0.0.1:8080"
    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:8080"
    assert os.environ["https_proxy"] == "http://127.0.0.1:8080"
    assert os.environ["ALL_PROXY"] == "http://127.0.0.1:8080"


def test_configure_proxies_socks5() -> None:
    """configure_proxies recognizes SOCKS_PROXY and populates environment variables."""
    os.environ["SOCKS_PROXY"] = "socks5://127.0.0.1:2080"
    active = configure_proxies()

    assert active == "socks5://127.0.0.1:2080"
    assert os.environ["HTTPS_PROXY"] == "socks5://127.0.0.1:2080"
    assert os.environ["ALL_PROXY"] == "socks5://127.0.0.1:2080"


def test_get_chat_model_google_genai_with_proxy() -> None:
    """get_chat_model wires proxy settings into Google GenAI client_args."""
    os.environ["SOCKS_PROXY"] = "socks5://127.0.0.1:2080"
    model = get_chat_model("google_genai:gemini-3.8-flash", api_key="fake-key")

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.client_args == {"proxy": "socks5://127.0.0.1:2080"}
    assert model.temperature == 1.0


def test_get_chat_model_openai_with_proxy() -> None:
    """get_chat_model wires proxy settings into OpenAI httpx client."""
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:8080"
    model = get_chat_model("openai:gpt-4o-mini", api_key="fake-key")

    assert isinstance(model, ChatOpenAI)
    assert model.http_client is not None
    assert model.temperature == 0.0
