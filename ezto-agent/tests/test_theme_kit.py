"""Tests for Theme v2 kit install and manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.services.theme_kit import (
    install_theme_kit,
    load_component_kit_guide,
    load_theme_meta,
    read_theme_manifest,
    theme_list_entry,
    write_theme_manifest,
)
from backend.services.theme_service import apply_theme


def test_load_clay_warm_meta():
    meta = load_theme_meta("clay-warm")
    assert meta.get("schema") == "v2"
    assert meta.get("family") == "claymorphism"
    assert "tk-card" in (meta.get("capabilities") or [])


def test_theme_list_entry_clay_warm():
    from configs import settings

    entry = theme_list_entry(Path(settings.themes_dir) / "clay-warm")
    assert entry is not None
    assert entry["schema"] == "v2"
    assert entry["family"] == "claymorphism"


def test_install_v2_kit(tmp_path: Path):
    ppt = tmp_path / "presentation"
    (ppt / "src" / "styles").mkdir(parents=True)
    installed = install_theme_kit(ppt, "clay-warm")
    assert any("theme-kit.css" in p for p in installed)
    assert (ppt / "src" / "theme" / "COMPONENT-KIT.md").is_file()
    assert "tk-card" in (ppt / "src" / "styles" / "theme-kit.css").read_text(encoding="utf-8")


def test_install_v1_stubs(tmp_path: Path):
    ppt = tmp_path / "presentation"
    (ppt / "src" / "styles").mkdir(parents=True)
    install_theme_kit(ppt, "midnight-press")
    stub = (ppt / "src" / "styles" / "theme-kit.css").read_text(encoding="utf-8")
    assert "stub" in stub.lower() or "v1" in stub.lower()
    assert not (ppt / "src" / "theme" / "COMPONENT-KIT.md").exists()


def test_manifest_v2_roundtrip(tmp_path: Path):
    ppt = tmp_path / "presentation"
    ppt.mkdir()
    write_theme_manifest(ppt, "clay-warm", load_theme_meta("clay-warm"))
    manifest = read_theme_manifest(ppt)
    assert manifest is not None
    assert manifest["schema"] == "v2"
    assert manifest["id"] == "clay-warm"


def test_load_component_kit_guide(tmp_path: Path):
    ws = tmp_path
    ppt = ws / "presentation"
    (ppt / "src" / "styles").mkdir(parents=True)
    install_theme_kit(ppt, "clay-warm")
    write_theme_manifest(ppt, "clay-warm", load_theme_meta("clay-warm"))
    guide = load_component_kit_guide(ws)
    assert guide is not None
    assert "tk-card" in guide


def test_apply_theme_v2_clay_warm(tmp_path: Path):
    ws = tmp_path
    (ws / "presentation" / "src" / "styles").mkdir(parents=True)
    result = apply_theme(ws, "clay-warm")
    assert result.schema == "v2"
    assert result.kit_files
    manifest = json.loads((ws / "presentation" / ".theme").read_text(encoding="utf-8"))
    assert manifest["schema"] == "v2"


def test_theme_kit_brief_block(tmp_path: Path):
    from harness.services.theme_kit import theme_kit_brief_block, install_theme_kit, write_theme_manifest, load_theme_meta

    ws = tmp_path
    ppt = ws / "presentation"
    (ppt / "src" / "styles").mkdir(parents=True)
    install_theme_kit(ppt, "clay-warm")
    write_theme_manifest(ppt, "clay-warm", load_theme_meta("clay-warm"))
    block = theme_kit_brief_block(ws)
    assert block is not None
    assert "tk-card" in block
    assert "claymorphism" in block


def test_format_brief_includes_v2_kit(tmp_path: Path):
    from harness.workflow.chapter_brief import format_brief_for_prompt
    from harness.services.theme_kit import install_theme_kit, write_theme_manifest, load_theme_meta

    ws = tmp_path
    ppt = ws / "presentation"
    ppt.mkdir(parents=True)
    install_theme_kit(ppt, "clay-warm")
    write_theme_manifest(ppt, "clay-warm", load_theme_meta("clay-warm"))
    prompt = format_brief_for_prompt({"chapter_id": "hook", "expected_steps": 3}, "Hook", workspace_root=ws)
    assert "Theme Kit (v2" in prompt
    assert "COMPONENT-KIT" in prompt


def test_apply_theme_v1_midnight_press(tmp_path: Path):
    ws = tmp_path
    (ws / "presentation" / "src" / "styles").mkdir(parents=True)
    result = apply_theme(ws, "midnight-press")
    assert result.schema == "v1"
    raw = (ws / "presentation" / ".theme").read_text(encoding="utf-8").strip()
    data = json.loads(raw) if raw.startswith("{") else {"id": raw}
    assert data.get("id", raw) == "midnight-press"
