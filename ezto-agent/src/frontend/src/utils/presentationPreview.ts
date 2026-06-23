import type { WorkflowState } from "../api/client";

/** Chapter 1 user checkpoint passed (风格锚点验收通过). */
export function isChapter1Accepted(state: WorkflowState): boolean {
  const conf = state.user_confirmations?.checkpoint_chapter_1;
  if (!conf || typeof conf !== "object") return false;
  return (conf as { approved?: boolean }).approved === true;
}

export function resolvePreviewHighlightIndex(state: WorkflowState): number {
  const raw = (state as WorkflowState & { current_chapter_index?: number })
    .current_chapter_index;
  if (typeof raw === "number" && raw >= 1) return raw - 1;
  return 0;
}

export function buildPresentationPreviewUrl(
  baseUrl: string,
  threadId: string,
  highlightIndex = 0,
): string {
  try {
    const url = new URL(baseUrl);
    url.searchParams.set("wid", threadId);
    url.searchParams.set("highlight", String(highlightIndex));
    url.searchParams.set("t", String(Date.now()));
    return url.toString();
  } catch {
    const sep = baseUrl.includes("?") ? "&" : "?";
    return `${baseUrl}${sep}wid=${encodeURIComponent(threadId)}&highlight=${highlightIndex}&t=${Date.now()}`;
  }
}

export function shouldShowPresentationPreviewFab(
  state: WorkflowState,
  interruptType?: string,
): boolean {
  if (!state.presentation_url) return false;
  if (!isChapter1Accepted(state)) return false;
  if (
    interruptType === "checkpoint_chapter_1" ||
    interruptType === "checkpoint_chapter_n" ||
    interruptType === "checkpoint_remaining_batch"
  ) {
    return false;
  }
  return true;
}
