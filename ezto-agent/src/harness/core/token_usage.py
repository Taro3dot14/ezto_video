"""Per-workflow LLM token usage tracking (by model)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Callable

_thread_ctx: ContextVar[str | None] = ContextVar("workflow_thread_id", default=None)
_record_handler: Callable[[str, str, dict[str, int]], None] | None = None


def empty_usage() -> dict[str, Any]:
    return {
        "revision": 0,
        "by_model": {},
        "total": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "calls": 0,
        },
    }


def merge_usage(
    current: dict[str, Any] | None,
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict[str, Any]:
    usage = empty_usage()
    if current:
        usage["revision"] = int(current.get("revision", 0))
        usage["by_model"] = {
            k: dict(v) for k, v in (current.get("by_model") or {}).items()
        }
        usage["total"] = dict(current.get("total") or empty_usage()["total"])

    bucket = usage["by_model"].setdefault(
        model,
        {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "calls": 0,
        },
    )
    bucket["prompt_tokens"] += prompt_tokens
    bucket["completion_tokens"] += completion_tokens
    bucket["total_tokens"] += prompt_tokens + completion_tokens
    bucket["calls"] += 1

    usage["total"]["prompt_tokens"] += prompt_tokens
    usage["total"]["completion_tokens"] += completion_tokens
    usage["total"]["total_tokens"] += prompt_tokens + completion_tokens
    usage["total"]["calls"] += 1
    usage["revision"] += 1
    return usage


def set_token_record_handler(
    handler: Callable[[str, str, dict[str, int]], None],
) -> None:
    global _record_handler
    _record_handler = handler


def bind_workflow_thread(thread_id: str | None) -> Token:
    return _thread_ctx.set(thread_id)


def reset_workflow_thread(token: Token) -> None:
    _thread_ctx.reset(token)


def record_api_usage(model: str, data: dict[str, Any]) -> None:
    """Record token usage from a chat/completions response body."""
    thread_id = _thread_ctx.get()
    if not thread_id or _record_handler is None:
        return
    raw = data.get("usage") or {}
    prompt = int(raw.get("prompt_tokens") or 0)
    completion = int(raw.get("completion_tokens") or 0)
    if prompt == 0 and completion == 0:
        return
    _record_handler(
        thread_id,
        model,
        {"prompt_tokens": prompt, "completion_tokens": completion},
    )
