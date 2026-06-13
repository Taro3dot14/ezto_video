"""Harness configuration."""

from __future__ import annotations

from pathlib import Path

_DEFAULT_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "services" / "tools" / "scripts"
_RESOURCES_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


def get_scripts_dir() -> Path:
    return _DEFAULT_SCRIPTS_DIR


def get_references_dir() -> Path:
    return _RESOURCES_DIR / "references"


def get_themes_dir() -> Path:
    return _RESOURCES_DIR / "themes"


def get_templates_dir() -> Path:
    return _RESOURCES_DIR / "templates"
