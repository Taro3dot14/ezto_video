import {
  resolvePresentationPreviewUrl,
  resolvePreviewHighlightIndex,
  shouldShowPresentationPreviewFab,
} from "../utils/presentationPreview";
import ThemeSwitcherPopover from "./ThemeSwitcherPopover";
import type { WorkflowState } from "../api/client";

interface Props {
  state: WorkflowState;
  threadId: string;
  interruptType?: string;
  previewCacheKey?: number;
  onThemeApplied?: (themeId: string) => void;
}

export default function PresentationPreviewFab({
  state,
  threadId,
  interruptType,
  previewCacheKey,
  onThemeApplied,
}: Props) {
  if (!shouldShowPresentationPreviewFab(state, interruptType)) {
    return null;
  }

  const href =
    resolvePresentationPreviewUrl(state, threadId, undefined, previewCacheKey) ?? "";
  if (!href) return null;

  const highlightIndex = resolvePreviewHighlightIndex(state);

  return (
    <div className="wf-preview-fab-wrap" role="presentation">
      <ThemeSwitcherPopover
        threadId={threadId}
        selectedTheme={state.selected_theme}
        visible
        onThemeApplied={onThemeApplied ?? (() => {})}
      />
      <a
        className="wf-preview-fab"
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="预览演示网页"
        title={`在新标签页打开演示（定位第 ${highlightIndex + 1} 章）`}
      >
        <span className="wf-preview-fab-icon" aria-hidden>
          <svg viewBox="0 0 24 24" width="22" height="22">
            <path
              d="M8 5v14l11-7L8 5z"
              fill="currentColor"
            />
          </svg>
        </span>
        <span className="wf-preview-fab-text">
          <span className="wf-preview-fab-label">预览</span>
          <span className="wf-preview-fab-hint">演示网页</span>
        </span>
      </a>
    </div>
  );
}
