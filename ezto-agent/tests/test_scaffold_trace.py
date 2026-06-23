"""Scaffold stdout lines pushed to execution trace."""

from harness.services.tools.scaffold import _scaffold_line_for_trace


def test_scaffold_trace_includes_progress():
    assert _scaffold_line_for_trace("▸ [1/4] 创建 Vite + React + TS 项目 → presentation")
    assert _scaffold_line_for_trace("✓ 依赖就绪（缓存）")
    assert _scaffold_line_for_trace("  · 命中依赖缓存，链接 node_modules")


def test_scaffold_trace_includes_summary():
    assert _scaffold_line_for_trace("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    assert _scaffold_line_for_trace("  ✓ 演示项目已就绪")
    assert _scaffold_line_for_trace("  预览      http://localhost:5202")
    assert _scaffold_line_for_trace("  开发      cd presentation && npm run dev")


def test_scaffold_trace_skips_npm_noise():
    assert not _scaffold_line_for_trace("npm install")
    assert not _scaffold_line_for_trace("npm run dev")
    assert not _scaffold_line_for_trace("")
