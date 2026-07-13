"""Application configuration via pydantic-settings.
"""

from __future__ import annotations

from pathlib import Path

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ChapterBuildMode = Literal["sub_agent", "agent_team"]

CHAPTER_BUILD_MODE_LABELS: dict[str, str] = {
    "sub_agent": "Sub Agent 模式",
    "agent_team": "Agent Team 模式",
}

# .env 在项目根，settings.py 在 src/configs/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = str(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
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
        "http://localhost:5202",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5202",
    ]

    # ── LLM ──
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    # Per-role routing (falls back to deepseek_model when empty)
    deepseek_model_content: str = "deepseek-v4-flash"
    deepseek_model_web_build: str = "deepseek-v4-pro"
    # DeepSeek V4 allows max_tokens in [1, 393216].
    deepseek_max_tokens: int = 393_216
    deepseek_temperature: float = 0.7

    @field_validator("deepseek_max_tokens", mode="after")
    @classmethod
    def _clamp_deepseek_max_tokens(cls, v: int) -> int:
        return max(1, min(v, 393_216))

    # ── TTS ──
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_tts_model: str = "tts-1"
    minimax_api_key: str = ""

    # ── Presentation dev server ──
    presentation_port: int = 5202

    # ── WebBuildAgent ──
    web_build_agent_max_iterations: int = 50
    # Chapter implementation mode (see harness/agent/chapter_build.py):
    #   sub_agent   — Builder → Reviewer 子 Agent → Repair → Verify
    #   agent_team  — Builder → [Reviewer → 三方会议 → Repair]* → Verify
    chapter_build_mode: ChapterBuildMode = "sub_agent"
    chapter_review_max_rounds: int = 4   # Review ↔ Repair cycles (initial + rechecks)
    chapter_repair_max_rounds: int = 4   # Max Repair attempts per chapter build

    @field_validator("chapter_build_mode", mode="before")
    @classmethod
    def _normalize_chapter_build_mode(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        legacy = {
            "self_review": "sub_agent",
            "sub_agent_review": "sub_agent",
            "team_discuss": "agent_team",
        }
        return legacy.get(v.strip(), v)

    # ── Phase 1 content (script.md / outline.md validate-repair loop) ──
    content_script_max_repair_retries: int = 5
    content_outline_max_repair_retries: int = 5

    # ── Agent Tool ──
    agent_tool_json_max_length: int = -1  # -1: no limit
    agent_use_native_tools: bool = True
    # Read-tool output shaping (read_file, review_chapter_bundle, etc.)
    agent_read_max_lines: int = -1        # truncate when line count exceeds this (≤0 = no limit)
    agent_read_head_lines: int = 30       # lines kept from the start after truncation
    agent_read_tail_lines: int = 20       # lines kept from the end after truncation

    # ── 路径（全部绝对路径，不依赖 CWD） ──
    project_root: str = str(_PROJECT_ROOT)
    workspace_root: str = str(_PROJECT_ROOT / "runtime" / "workspace")
    logs_dir: str = str(_PROJECT_ROOT / "runtime" / "logs")
    assets_dir: str = str(_PROJECT_ROOT / "assets")
    references_dir: str = str(_PROJECT_ROOT / "assets" / "references")
    themes_dir: str = str(_PROJECT_ROOT / "assets" / "themes")
    templates_dir: str = str(_PROJECT_ROOT / "assets" / "templates")
    cmd_dir: str = str(_PROJECT_ROOT / "src" / "harness" / "services" / "cmd")

settings = Settings()  # singleton
