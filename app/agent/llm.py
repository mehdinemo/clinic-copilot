"""LLM initialization helper using langchain init_chat_model."""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()


def get_chat_model(model_spec: Optional[str] = None) -> BaseChatModel:
    """Initialize chat model dynamically based on environment configuration or parameter.

    Accepts format 'provider:model' (e.g. 'openai:gpt-4o-mini') or standard model name.
    """
    raw_spec = model_spec or os.environ.get("LLM_MODEL", "openai:gpt-4o-mini")
    raw_spec = raw_spec.strip()

    if ":" in raw_spec:
        provider, model_name = raw_spec.split(":", 1)
        return init_chat_model(
            model=model_name,
            model_provider=provider,
            temperature=0,
            timeout=30,
            max_retries=2,
        )

    return init_chat_model(
        model=raw_spec,
        temperature=0,
        timeout=30,
        max_retries=2,
    )
