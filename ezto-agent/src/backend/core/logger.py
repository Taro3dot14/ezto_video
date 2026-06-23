"""Structured logging for the ezto-agent application.

Logs to three destinations:
  - Console (stderr, colored, INFO+)
  - Main log file  (logs/ezto-agent.log, rotating, DEBUG+)
  - LLM interaction log (logs/llm.log, append-only, full prompt/response)

Configuration via environment variables:
    LOG_LEVEL=DEBUG          # default: INFO  (console threshold)
    LOG_DIR=logs             # default: logs/ (relative to project root)
    LOG_FILE=ezto-agent.log # default

Usage:
    from backend.core.logger import logger
    logger.info("Node started")

    # Log full LLM interaction
    from backend.core.logger import log_llm_interaction
    log_llm_interaction(messages, response, model="...", duration_ms=...)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from configs import settings

# ── Configuration from environment ──
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_LOG_DIR = os.environ.get("LOG_DIR", str(settings.logs_dir))
_LOG_FILE = os.environ.get("LOG_FILE", "ezto-agent.log")


def _ensure_dir(path: str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _setup_logger() -> logging.Logger:
    """Create and configure the application logger."""
    logger = logging.getLogger("ezto")
    logger.setLevel(logging.DEBUG)  # root level DEBUG so handlers can filter

    # Avoid duplicate handlers on reload (uvicorn --reload)
    if logger.handlers:
        return logger

    main_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Console handler (stderr, colored level) ──
    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))

    class ColorFormatter(logging.Formatter):
        """Simple color formatter: highlight level in ANSI."""

        _COLORS = {
            "DEBUG": "\033[36m",
            "INFO": "\033[32m",
            "WARNING": "\033[33m",
            "ERROR": "\033[31m",
            "CRITICAL": "\033[41m",
        }
        _RESET = "\033[0m"

        def format(self, record: logging.LogRecord) -> str:
            levelname = record.levelname
            color = self._COLORS.get(levelname, "")
            if color:
                record.levelname = f"{color}{levelname}{self._RESET}"
            return super().format(record)

    console.setFormatter(ColorFormatter(
        fmt="%(asctime)s [%(levelname)-17s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # ── Main file handler (rotating, 10 MB, keep 5, DEBUG+) ──
    log_dir = _ensure_dir(_LOG_DIR)
    file_path = log_dir / _LOG_FILE
    file_handler = RotatingFileHandler(
        str(file_path), maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(main_formatter)
    logger.addHandler(file_handler)

    return logger


logger = _setup_logger()

# ── LLM interaction log (separate file, full content) ──


def _setup_llm_logger() -> logging.Logger:
    """Create a dedicated logger for full LLM prompt/response pairs."""
    llm_log = logging.getLogger("ezto.llm")
    llm_log.setLevel(logging.DEBUG)
    llm_log.propagate = False  # don't send to root logger

    if llm_log.handlers:
        return llm_log

    log_dir = _ensure_dir(_LOG_DIR)
    llm_path = log_dir / "llm.log"
    handler = RotatingFileHandler(
        str(llm_path), maxBytes=50 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    llm_log.addHandler(handler)
    return llm_log


_llm_logger = _setup_llm_logger()


def log_llm_interaction(
    *,
    messages: list[dict[str, str]],
    response: str,
    model: str,
    temperature: float | None = None,
    duration_ms: float = 0,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Log a complete LLM interaction (full prompt + response) to the LLM log file.

    The log format is designed for easy grep/search:
      [TIMESTAMP] === LLM CALL === model=... duration=...ms success=...
      --- REQUEST ---
      <role>: <content>
      --- RESPONSE ---
      <response text>
      --- END ---
    """
    lines = [
        "═══════════════════════════════════════════════════════════════════",
        f"LLM CALL  model={model}  duration={duration_ms:.0f}ms  success={success}",
    ]
    if temperature is not None:
        lines.append(f"temperature={temperature}")
    if error:
        lines.append(f"error={error}")
    lines.append("")
    lines.append("─── REQUEST ───")
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)
        # Truncate overly long single messages for readability
        if len(content) > 10000:
            content = content[:5000] + f"\n... [TRUNCATED, total {len(content)} chars] ...\n" + content[-5000:]
        lines.append(f"[{role}]")
        if msg.get("tool_calls"):
            lines.append(f"(tool_calls: {len(msg['tool_calls'])})")
        if msg.get("tool_call_id"):
            lines.append(f"(tool_call_id: {msg['tool_call_id']})")
        lines.append(content)
        lines.append("")
    lines.append("─── RESPONSE ───")
    if success:
        if len(response) > 10000:
            lines.append(response[:5000] + f"\n... [TRUNCATED, total {len(response)} chars] ...\n" + response[-5000:])
        else:
            lines.append(response)
    else:
        lines.append(f"[ERROR] {error or 'unknown'}")
    lines.append("")
    lines.append("─── END ───")
    lines.append("")

    _llm_logger.info("\n".join(lines))


# ── Convenience helpers ──


def log_llm_call(model: str, message_count: int, char_count: int, success: bool, duration_ms: float) -> None:
    """Log an LLM API call summary (to main log)."""
    status = "OK" if success else "FAIL"
    logger.info(
        "LLM [%s] %d msgs, %d chars → %s (%.1fs)",
        model, message_count, char_count, status, duration_ms / 1000,
    )


def log_api_request(method: str, path: str, status: int, duration_ms: float) -> None:
    """Log an incoming API request."""
    logger.info(
        "API %s %s → %d (%.0fms)",
        method, path, status, duration_ms,
    )
