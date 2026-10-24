"""Core context-usage calculation shared by the SDK, CLI, and MCP server."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from . import tokenizers
from .file_io import iter_log_files, load_messages
from .models import ModelConfig, get_model_config

DEFAULT_MODEL = "gpt-4o"

_ROLE_BUCKETS = {
    "system": "system_tokens",
    "developer": "system_tokens",
    "user": "user_tokens",
    "assistant": "assistant_tokens",
    "tool": "tool_tokens",
    "function": "tool_tokens",
}


def audit(
    messages: Iterable[Mapping[str, Any]],
    model: str = DEFAULT_MODEL,
    *,
    context_window: int | None = None,
) -> dict[str, Any]:
    """Measure context usage of a completed conversation.

    Args:
        messages: Conversation messages in OpenAI-style chat format. Each item
            must be a mapping with at least a ``role``; ``content``,
            ``tool_calls``, and ``name`` are counted when present.
        model: A name from :data:`context_audit.MODEL_REGISTRY`. Versioned
            suffixes such as ``gpt-4o-2024-08-06`` are accepted.
        context_window: Optional override for the model's context window.

    Returns:
        A report dictionary with token totals, per-role breakdown, usage ratio,
        remaining tokens, and a risk level.
    """

    config = get_model_config(model)
    window = _resolve_context_window(context_window, config)
    message_list = _as_message_list(messages)

    breakdown = {
        "system_tokens": 0,
        "user_tokens": 0,
        "assistant_tokens": 0,
        "tool_tokens": 0,
    }

    for index, message in enumerate(message_list):
        if not isinstance(message, Mapping):
            raise TypeError(
                f"message at index {index} must be a mapping, got {type(message).__name__}"
            )
        bucket = _role_bucket(message, index)
        breakdown[bucket] += tokenizers.count_tokens(_message_text(message), config)

    total_tokens = sum(breakdown.values())
    usage_ratio = total_tokens / window

    return {
        "model": config.name,
        "context_window": window,
        "total_tokens": total_tokens,
        "usage_ratio": round(usage_ratio, 4),
        "usage_percent": f"{usage_ratio * 100:.1f}%",
        "remaining_tokens": max(window - total_tokens, 0),
        "breakdown": breakdown,
        "message_count": len(message_list),
        "level": _risk_level(usage_ratio),
        "warning": usage_ratio >= 0.80,
    }


def audit_file(
    path: str,
    model: str = DEFAULT_MODEL,
    *,
    context_window: int | None = None,
) -> dict[str, Any]:
    """Analyze a ``.json`` or ``.jsonl`` conversation log."""

    return audit(load_messages(path), model=model, context_window=context_window)


def audit_dir(
    directory: str,
    model: str = DEFAULT_MODEL,
    *,
    context_window: int | None = None,
) -> list[dict[str, Any]]:
    """Analyze every ``.json`` / ``.jsonl`` log in *directory*.

    Each report includes a ``file`` key identifying its source log.
    """

    reports: list[dict[str, Any]] = []
    for path in iter_log_files(directory):
        report = audit_file(path, model=model, context_window=context_window)
        reports.append({"file": str(path), **report})
    return reports


def _as_message_list(messages: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(messages, (str, bytes, Mapping)):
        raise TypeError("messages must be an iterable of message mappings")
    try:
        return list(messages)
    except TypeError as exc:
        raise TypeError("messages must be an iterable of message mappings") from exc


def _role_bucket(message: Mapping[str, Any], index: int) -> str:
    role = message.get("role")
    if not isinstance(role, str) or not role.strip():
        raise ValueError(f"message at index {index} is missing a string 'role' field")

    bucket = _ROLE_BUCKETS.get(role.strip().lower())
    if bucket is None:
        supported = ", ".join(sorted(_ROLE_BUCKETS))
        raise ValueError(
            f"unsupported role {role!r} at index {index}; supported roles: {supported}"
        )
    return bucket


def _message_text(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        parts = [content]
    elif content is None:
        parts = []
    else:
        parts = [json.dumps(content, ensure_ascii=False, separators=(",", ":"))]

    name = message.get("name")
    if isinstance(name, str) and name:
        parts.append(f"name:{name}")

    tool_calls = message.get("tool_calls")
    if tool_calls:
        parts.append(
            json.dumps(tool_calls, ensure_ascii=False, separators=(",", ":"), default=str)
        )

    return "\n".join(parts)


def _risk_level(usage_ratio: float) -> str:
    if usage_ratio >= 0.95:
        return "critical"
    if usage_ratio >= 0.80:
        return "high"
    if usage_ratio >= 0.60:
        return "medium"
    return "low"


def _resolve_context_window(override: int | None, config: ModelConfig) -> int:
    if override is None:
        return config.context_window
    if isinstance(override, bool) or not isinstance(override, int):
        raise TypeError("context_window must be an integer")
    if override <= 0:
        raise ValueError("context_window must be greater than 0")
    return override
