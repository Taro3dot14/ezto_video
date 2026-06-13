"""Application configuration via pydantic-settings.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    deepseek_max_tokens: int = 8192
    deepseek_temperature: float = 0.7

    # ── TTS ──
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_tts_model: str = "tts-1"
    minimax_api_key: str = ""

    # ── Presentation dev server ──
    presentation_port: int = 5202

    # ── WebBuildAgent ──
    web_build_agent_max_iterations: int = 50

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
