import type { WorkflowState } from "../api/client";

/** Chapter 1 user checkpoint passed (风格锚点验收通过). */
export function isChapter1Accepted(state: WorkflowState): boolean {
  const conf = state.user_confirmations?.checkpoint_chapter_1;
  if (!conf || typeof conf !== "object") return false;
  return (conf as { approved?: boolean }).approved === true;
}

export function resolvePreviewHighlightIndex(
  state: WorkflowState,
  interrupt?: Record<string, unknown> | null,
): number {
  const fromInterrupt = interrupt?.highlight_chapter_index;
  if (typeof fromInterrupt === "number" && fromInterrupt >= 0) {
    return fromInterrupt;
  }
  const chapterIndex = interrupt?.chapter_index;
  if (typeof chapterIndex === "number" && chapterIndex >= 1) {
    return chapterIndex - 1;
  }
  const raw = (state as WorkflowState & { current_chapter_index?: number })
    .current_chapter_index;
  if (typeof raw === "number" && raw >= 1) return raw - 1;
  return 0;
}

export function buildPresentationPreviewUrl(
  baseUrl: string,
  threadId: string,
  highlightIndex = 0,
  cacheKey?: number,
): string {
  try {
    const url = new URL(baseUrl);
    url.searchParams.set("wid", threadId);
    url.searchParams.set("highlight", String(highlightIndex));
    url.searchParams.set("t", String(cacheKey ?? Date.now()));
    return url.toString();
  } catch {
    const sep = baseUrl.includes("?") ? "&" : "?";
    const t = cacheKey ?? Date.now();
    return `${baseUrl}${sep}wid=${encodeURIComponent(threadId)}&highlight=${highlightIndex}&t=${t}`;
  }
}

/** True when dev server URL is set and at least one chapter build is on disk / in progress. */
export function canPreviewPresentation(state: WorkflowState): boolean {
  if (!state.presentation_url) return false;

  const activity = [
    ...(state.completed_nodes ?? []),
    state.current_node ?? "",
    ...((state.errors ?? []) as { node?: string; phase?: string }[]).flatMap((e) => [
      e.node ?? "",
      e.phase ?? "",
    ]),
  ].join(" ");

  if (/build_chapter|checkpoint_chapter|wv_scaffold_presentation/.test(activity)) {
    return true;
  }
  if (state.pending_interrupt?.preview_url) return true;
  return isChapter1Accepted(state);
}

export function shouldShowPresentationPreviewFab(
  state: WorkflowState,
  _interruptType?: string,
): boolean {
  return canPreviewPresentation(state);
}

export function resolvePresentationPreviewUrl(
  state: WorkflowState,
  threadId: string,
  interrupt?: Record<string, unknown> | null,
  cacheKey?: number,
): string | null {
  const fromInterrupt = interrupt?.preview_url;
  if (typeof fromInterrupt === "string" && fromInterrupt) {
    return fromInterrupt;
  }
  if (!state.presentation_url) return null;
  if (!canPreviewPresentation(state)) return null;
  return buildPresentationPreviewUrl(
    state.presentation_url,
    threadId,
    resolvePreviewHighlightIndex(state, interrupt),
    cacheKey,
  );
}
