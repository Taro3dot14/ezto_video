"""Tests for deterministic manual pre-checks."""

from harness.services.tools.craft.craft_precheck import (
    run_manual_prechecks,
)


def test_list_one_per_step_fails_multi_active():
    tsx = """
    export default function Ch({ step }) {
      if (step === 0) return (
        <ListGrid>
          <GridSlot state="active">A</GridSlot>
          <GridSlot state="active">B</GridSlot>
        </ListGrid>
      );
    }
    """
    hints = run_manual_prechecks(tsx=tsx, css="", narrations_text='export default ["a"];')
    assert hints["LIST_ONE_PER_STEP"]["pass"] is False


def test_list_one_per_step_passes_without_grid():
    tsx = 'if (step === 0) return <div className="lx-cover-body">Hi</div>;'
    hints = run_manual_prechecks(tsx=tsx, css="", narrations_text='export default ["a"];')
    assert hints["LIST_ONE_PER_STEP"]["pass"] is True


def test_panel_width_passes_wide_panel():
    css = ".ch-panel { width: 78%; min-height: 400px; }"
    hints = run_manual_prechecks(tsx="x", css=css, narrations_text="")
    assert hints["PANEL_WIDTH"]["pass"] is True


def test_panel_width_fails_narrow_panel():
    css = ".ch-card { width: 40%; }"
    hints = run_manual_prechecks(tsx="x", css=css, narrations_text="")
    assert hints["PANEL_WIDTH"]["pass"] is False


def test_animation_duration_within_narration():
    tsx = """
    if (step === 0) return <div className="mot-stamp-drop" style={{animationDuration: "0.8s"}} />;
    """
    css = "@keyframes x { from {} to {} } .mot-stamp-drop { animation: x 0.8s; }"
    narr = 'export default [\n  "这是一段足够长的口播文案用于测试动画时长",\n];'
    hints = run_manual_prechecks(tsx=tsx, css=css, narrations_text=narr)
    assert hints["ANIMATION_DURATION"]["pass"] is True
