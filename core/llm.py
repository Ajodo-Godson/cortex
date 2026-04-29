"""Shared LLM client builder for Cortex agents."""

from __future__ import annotations

import os

try:
    import anthropic as _anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

DEFAULT_MODEL = "claude-opus-4-7"


def build_client(model: str) -> tuple[str, object]:
    """Return (provider, client) for the given model name.

    Routing:
      claude-*      → Anthropic SDK  (ANTHROPIC_API_KEY or CORTEX_API_KEY)
      anything else → OpenAI-compat  (OPENAI_API_KEY or CORTEX_API_KEY,
                                       CORTEX_BASE_URL for custom endpoints)
    """
    api_key_override = os.environ.get("CORTEX_API_KEY")

    if model.startswith("claude-"):
        if not _HAS_ANTHROPIC:
            raise RuntimeError(
                "Install the anthropic package to use Claude models: "
                "pip install 'cortex[anthropic]'"
            )
        api_key = api_key_override or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Set ANTHROPIC_API_KEY (or CORTEX_API_KEY) to use Claude models."
            )
        kwargs: dict[str, str] = {"api_key": api_key}
        anthropic_base = os.environ.get("ANTHROPIC_BASE_URL")
        if anthropic_base:
            kwargs["base_url"] = anthropic_base
        return "anthropic", _anthropic.Anthropic(**kwargs)

    try:
        import openai as _openai  # noqa: PLC0415
    except ImportError:
        raise RuntimeError(
            f"Install the openai package to use {model}: pip install 'cortex[openai]'"
        )
    api_key = api_key_override or os.environ.get("OPENAI_API_KEY", "unused")
    base_url = os.environ.get("CORTEX_BASE_URL")
    oa_kwargs: dict[str, str] = {"api_key": api_key}
    if base_url:
        oa_kwargs["base_url"] = base_url
    return "openai", _openai.OpenAI(**oa_kwargs)
