"""Application configuration via pydantic-settings.

Usage:
    from app.core import settings, llm

    # Access any setting as an attribute
    settings.openai_api_key
    settings.port

    # LLM chat completion (DeepSeek, OpenAI-compatible)
    response = llm.chat(messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"},
    ])
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Server ──
    host: str = "127.0.0.1"
    port: int = 8001

    # ── CORS ──
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    # ── DeepSeek LLM ──
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_max_tokens: int = 8192
    deepseek_temperature: float = 0.7

    # ── OpenAI TTS ──
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_tts_model: str = "tts-1"

    # ── MiniMax TTS ──
    minimax_api_key: str = ""

    # ── Workspace ──
    workspace_root: str = "workspace"

    # ── Project root for finding refs/themes/scripts ──
    project_root: str = str(Path(".").resolve())


settings = Settings()  # singleton

