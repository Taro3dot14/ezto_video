/** Mirror of backend node_catalog.py for plan milestones. */

const GROUP_LABELS: Record<string, string> = {
  script: "口播稿优化",
  outline: "大纲优化",
};

export { GROUP_LABELS };

const PHASE_NUMERALS = ["一", "二", "三", "四", "五", "六", "七", "八", "九"] as const;

export const PHASE_LABELS: Record<string, string> = {
  phase1: "脚本编写",
  phase2: "网页开发",
  phase3: "音频合成",
  phase4: "录屏后期",
};

/** Canonical display labels — no emoji; shared by plan + think panels. */
export const NODE_META: Record<string, { label: string; phase: string; group?: string }> = {
  wv_identify_input: { label: "识别输入类型", phase: "phase1" },
  wv_prepare_source_files: { label: "生成口播稿和大纲", phase: "phase1" },
  plan_script_optimize: { label: "口播稿优化", phase: "phase1" },
  plan_outline_optimize: { label: "大纲优化", phase: "phase1" },
  wv_validate_script: { label: "核对口播稿", phase: "phase1", group: "script" },
  wv_repair_script: { label: "润色口播稿", phase: "phase1", group: "script" },
  wv_validate_outline: { label: "核对大纲", phase: "phase1", group: "outline" },
  wv_repair_outline: { label: "调整大纲", phase: "phase1", group: "outline" },
  wv_checkpoint_plan: { label: "确认计划", phase: "phase1" },
  wv_scaffold_presentation: { label: "页面初始化", phase: "phase2" },
  wv_build_chapter_1: { label: "构建页面-第1章", phase: "phase2" },
  wv_checkpoint_chapter_1: { label: "验收第 1 章", phase: "phase2" },
  wv_build_chapter_n: { label: "构建页面", phase: "phase2" },
  wv_checkpoint_chapter_n: { label: "验收章节", phase: "phase2" },
  wv_checkpoint_remaining_batch: { label: "批量验收", phase: "phase2" },
  wv_transition_to_phase3: { label: "进入音频阶段", phase: "phase2" },
  wv_checkpoint_audio: { label: "是否合成音频", phase: "phase3" },
  wv_extract_narrations: { label: "提取旁白", phase: "phase3" },
  wv_checkpoint_audio_segments: { label: "检查音频分段", phase: "phase3" },
  wv_synthesize_audio: { label: "合成音频", phase: "phase3" },
  wv_report_audio_anomalies: { label: "音频异常报告", phase: "phase3" },
  wv_recording_guidance: { label: "录屏指引", phase: "phase4" },
};

export const PLAN_ORDER = [
  "wv_identify_input",
  "wv_prepare_source_files",
  "plan_script_optimize",
  "plan_outline_optimize",
  "wv_checkpoint_plan",
  "wv_scaffold_presentation",
  "wv_build_chapter_1",
  "wv_checkpoint_chapter_1",
  "wv_build_chapter_n",
  "wv_transition_to_phase3",
  "wv_extract_narrations",
  "wv_synthesize_audio",
  "wv_recording_guidance",
] as const;

export const TOTAL_NODES = Object.keys(NODE_META).length;

/** Runtime graph nodes (exclude plan-only virtual milestones). */
const RUNTIME_NODE_IDS = Object.keys(NODE_META).filter(
  (id) => !id.startsWith("plan_"),
);

/** Validate/repair pairs merge into one display group in the thinking panel. */
const MERGED_REPAIR_NODE_IDS = new Set([
  "wv_repair_script",
  "wv_repair_outline",
]);

/** Fixed total for 环节 counter in the thinking panel header. */
export const THINK_STAGE_COUNT =
  RUNTIME_NODE_IDS.length - MERGED_REPAIR_NODE_IDS.size;

function stripLeadingEmoji(label: string): string {
  return label.replace(/^\S+\s+/, "").trim() || label;
}

/** Shared label for plan steps, think cards, topbar, and sidebar. */
export function displayNodeLabel(nodeId: string | null | undefined): string {
  if (!nodeId) return "—";
  const m = NODE_META[nodeId];
  if (!m) {
    return nodeId.replace(/^wv_/, "").replace(/_/g, " ");
  }
  if (m.group) {
    return GROUP_LABELS[m.group] ?? stripLeadingEmoji(m.label);
  }
  return m.label;
}

export function displayPlanLabel(nodeId: string): string {
  return displayNodeLabel(nodeId);
}

export const PLAN_MILESTONES = PLAN_ORDER.map((node) => ({
  node,
  label: displayPlanLabel(node),
}));

export function displayPhaseLabel(phase: string): string {
  const label = PHASE_LABELS[phase];
  if (!label) return phase;
  const num = Number.parseInt(phase.replace(/^phase/, ""), 10);
  const cn = Number.isFinite(num) && num >= 1 ? PHASE_NUMERALS[num - 1] ?? String(num) : phase;
  return `阶段${cn}：${label}`;
}

export function formatElapsed(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
