"""Unified LLM client for DeepSeek API (OpenAI-compatible).

Handles chat completion, streaming, and error recovery.
All graph nodes should use this module rather than calling an LLM directly.

Usage:
    from app.core import llm

    reply = llm.chat(messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "What is the capital of France?"},
    ])
"""

from __future__ import annotations

import concurrent.futures
import json
import time
from typing import Any, Generator

import httpx

from . import settings
from .logger import logger, log_llm_call, log_llm_interaction

# Shared thread pool for LLM calls with hard timeout
_LLM_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="llm",
)


def _http_post(
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    read_timeout: float,
) -> httpx.Response:
    """Execute a single HTTP POST (runs in thread pool)."""
    timeout = httpx.Timeout(
        connect=30.0, read=read_timeout, write=30.0, pool=15.0,
    )
    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    return resp


def chat(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    retries: int = 2,
    timeout: float = 300.0,
    read_timeout: float = 120.0,
) -> str:
    """Send a chat completion request to DeepSeek API.

    Logs the full prompt and response to logs/llm.log for debugging.
    Uses a thread-pool background worker to enforce a hard total timeout.

    Args:
        messages: Message list, e.g. [{"role": "system", ...}, {"role": "user", ...}].
        model: Model ID, defaults to settings.deepseek_model.
        temperature: Sampling temperature, defaults to settings value.
        max_tokens: Max tokens in response, defaults to settings value.
        retries: Number of retries on failure (total attempts = 1 + retries).
        timeout: Hard total timeout for the entire call (including retries).
        read_timeout: Per-attempt read idle timeout (max seconds between bytes).

    Returns:
        Response content text.

    Raises:
        RuntimeError: If all retries are exhausted or total timeout exceeded.
    """
    if not settings.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY not configured. "
            "Set it in .env or export DEEPSEEK_API_KEY=sk-..."
        )

    body = _build_body(messages, model, temperature, max_tokens)
    model_name = body.get("model", "?")
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = _headers()

    total_chars = sum(len(m.get("content", "")) for m in messages)
    t0 = time.perf_counter()
    last_err: Exception | None = None

    deadline = t0 + timeout

    for attempt in range(1 + retries):
        try:
            remaining = max(deadline - time.perf_counter(), 5.0)  # at least 5s per attempt

            if remaining < 5.0 and attempt > 0:
                raise TimeoutError(f"LLM call timed out after {timeout:.0f}s total (no time for retry)")

            logger.debug("LLM request [%s] attempt=%d/%d msgs=%d chars=%d remaining=%.0fs",
                         model_name, attempt + 1, retries + 1, len(messages), total_chars,
                         remaining)

            future = _LLM_POOL.submit(
                _http_post, url, headers, body, read_timeout,
            )
            resp = future.result(timeout=remaining)
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            elapsed = (time.perf_counter() - t0) * 1000

            if elapsed > 30_000:  # warning for slow calls (>30s)
                logger.warning("LLM [%s] slow call: %.1fs chars=%d",
                               model_name, elapsed / 1000, total_chars)

            log_llm_call(model_name, len(messages), total_chars, True, elapsed)
            log_llm_interaction(
                messages=messages, response=content, model=model_name,
                temperature=temperature, duration_ms=elapsed, success=True,
            )
            return content

        except concurrent.futures.TimeoutError:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning("LLM attempt %d/%d TIMEOUT after %.0fms (limit=%.0fs)",
                           attempt + 1, retries + 1, elapsed, timeout)
            if attempt < retries and time.perf_counter() - t0 < timeout:
                continue
            last_err = TimeoutError(f"LLM call timed out after {timeout:.0f}s total")

        except (httpx.HTTPStatusError, httpx.RequestError, KeyError, json.JSONDecodeError,
                concurrent.futures.CancelledError) as e:
            last_err = e
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning("LLM attempt %d/%d failed after %.0fms: %s",
                           attempt + 1, retries + 1, elapsed, e)
            if attempt < retries:
                if time.perf_counter() - t0 >= timeout:
                    last_err = TimeoutError(f"LLM call timed out after {timeout:.0f}s total")
                    break
                time.sleep(min(1.5 ** attempt, remaining - 5.0))
                continue

    elapsed = (time.perf_counter() - t0) * 1000
    log_llm_call(model_name, len(messages), total_chars, False, elapsed)
    log_llm_interaction(
        messages=messages, response="", model=model_name,
        temperature=temperature, duration_ms=elapsed, success=False,
        error=str(last_err),
    )
    raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last_err}")


def chat_stream(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    retries: int = 2,
) -> Generator[str, None, None]:
    """Stream a chat completion from DeepSeek API.

    Yields content delta strings as they arrive.
    Full prompt/response is logged to logs/llm.log on completion.
    """
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")

    body = _build_body(messages, model, temperature, max_tokens)
    body["stream"] = True
    model_name = body.get("model", "?")
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = _headers()

    total_chars = sum(len(m.get("content", "")) for m in messages)
    t0 = time.perf_counter()
    last_err: Exception | None = None
    chunks: list[str] = []

    for attempt in range(1 + retries):
        try:
            logger.debug("LLM stream [%s] attempt=%d/%d msgs=%d chars=%d",
                         model_name, attempt + 1, retries + 1, len(messages), total_chars)
            with httpx.Client(timeout=120) as client:
                with client.stream("POST", url, headers=headers, json=body) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line.removeprefix("data: ").strip()
                        if payload == "[DONE]":
                            full = "".join(chunks)
                            elapsed = (time.perf_counter() - t0) * 1000
                            log_llm_call(model_name, len(messages), total_chars, True, elapsed)
                            log_llm_interaction(
                                messages=messages, response=full, model=model_name,
                                temperature=temperature, duration_ms=elapsed, success=True,
                            )
                            return
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            chunks.append(delta)
                            yield delta
            return
        except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError) as e:
            last_err = e
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning("LLM stream attempt %d/%d failed after %.0fms: %s",
                           attempt + 1, retries + 1, elapsed, e)
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue

    elapsed = (time.perf_counter() - t0) * 1000
    log_llm_call(model_name, len(messages), total_chars, False, elapsed)
    log_llm_interaction(
        messages=messages, response="".join(chunks), model=model_name,
        temperature=temperature, duration_ms=elapsed, success=False,
        error=str(last_err),
    )
    raise RuntimeError(f"LLM stream failed after {retries + 1} attempts: {last_err}")


# ── Internal helpers ──


def _build_body(
    messages: list[dict[str, str]],
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
) -> dict[str, Any]:
    return {
        "model": model or settings.deepseek_model,
        "messages": list(messages),
        "temperature": temperature if temperature is not None else settings.deepseek_temperature,
        "max_tokens": max_tokens or settings.deepseek_max_tokens,
    }


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
