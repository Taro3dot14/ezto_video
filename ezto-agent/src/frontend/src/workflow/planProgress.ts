/** Plan milestone progress helpers (shared by plan panel + tests). */

export const PLAN_NODE_ALIASES: Record<string, string> = {
  wv_validate_script: "plan_script_optimize",
  wv_repair_script: "plan_script_optimize",
  wv_validate_outline: "plan_outline_optimize",
  wv_repair_outline: "plan_outline_optimize",
  wv_checkpoint_chapter_n: "wv_checkpoint_chapter_1",
  wv_checkpoint_remaining_batch: "wv_build_chapter_n",
  wv_checkpoint_audio: "wv_transition_to_phase3",
  wv_checkpoint_audio_segments: "wv_extract_narrations",
  wv_report_audio_anomalies: "wv_synthesize_audio",
};

export function resolvePlanIndex(
  currentNode: string | null,
  planOrder: string[],
): number {
  if (!currentNode) return -1;
  const direct = planOrder.indexOf(currentNode);
  if (direct >= 0) return direct;
  const alias = PLAN_NODE_ALIASES[currentNode];
  if (alias) return planOrder.indexOf(alias);
  return -1;
}

function highestCompletedPlanIndex(
  completedNodes: string[],
  planOrder: string[],
): number {
  let max = -1;
  for (const node of completedNodes) {
    let idx = planOrder.indexOf(node);
    if (idx < 0) {
      const alias = PLAN_NODE_ALIASES[node];
      if (alias) idx = planOrder.indexOf(alias);
    }
    if (idx >= 0) max = Math.max(max, idx);
  }
  return max;
}

export type PlanStepStatus = "done" | "current" | "pending";

export function buildPlanStepStatuses(
  planOrder: string[],
  completedNodes: string[],
  currentNode: string | null,
): PlanStepStatus[] {
  const currentIdx = resolvePlanIndex(currentNode, planOrder);
  const aliasMax = highestCompletedPlanIndex(completedNodes, planOrder);

  return planOrder.map((node, index) => {
    if (currentIdx === index || currentNode === node) return "current";
    if (currentIdx > index) return "done";
    if (currentIdx < 0 && aliasMax > index) return "done";
    if (completedNodes.includes(node)) return "done";
    return "pending";
  });
}

export function planMetaCounts(
  planOrder: string[],
  completedNodes: string[],
  currentNode: string | null,
): { active: number; total: number } {
  const statuses = buildPlanStepStatuses(planOrder, completedNodes, currentNode);
  const done = statuses.filter((s) => s === "done").length;
  const hasCurrent = statuses.some((s) => s === "current");
  return {
    active: Math.min(done + (hasCurrent ? 1 : 0), planOrder.length),
    total: planOrder.length,
  };
}
