import type { ReactNode } from "react";

interface Props {
  open: boolean;
  collapsedLabel: string;
  onClose: () => void;
  onOpen: () => void;
  children: ReactNode;
}

export default function CheckpointReviewShell({
  open,
  collapsedLabel,
  onClose,
  onOpen,
  children,
}: Props) {
  if (!open) {
    return (
      <button
        type="button"
        className="wf-review-collapsed-btn"
        onClick={onOpen}
        aria-label={`打开${collapsedLabel}`}
        title="打开验收面板（工作流仍在此步骤等待，未推进）"
      >
        <span className="wf-review-collapsed-icon" aria-hidden>
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
            <path
              d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
            <rect
              x="9"
              y="3"
              width="6"
              height="4"
              rx="1"
              stroke="currentColor"
              strokeWidth="1.8"
            />
            <path d="M9 12h6M9 16h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </span>
        <span className="wf-review-collapsed-text">
          <span className="wf-review-collapsed-label">{collapsedLabel}</span>
          <span className="wf-review-collapsed-hint">点击继续验收</span>
        </span>
        <span className="wf-review-collapsed-dot" aria-hidden />
      </button>
    );
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label={collapsedLabel}>
      <div className="modal-card modal-card-dismissible">
        <button
          type="button"
          className="modal-close-btn"
          onClick={onClose}
          aria-label="收起验收面板"
          title="收起（不推进进度，可随时再打开）"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
            <path
              d="M6 6l12 12M18 6L6 18"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
        {children}
      </div>
    </div>
  );
}

export function chapterReviewCollapsedLabel(interrupt: Record<string, unknown>): string {
  if (interrupt.type === "checkpoint_remaining_batch") {
    return "批量验收";
  }
  const id = interrupt.chapter_id as string | undefined;
  const idx = interrupt.chapter_index as number | undefined;
  if (id) return `章节验收 · ${id}`;
  return `章节验收 · 第 ${idx ?? "?"} 章`;
}

export function isChapterReviewInterrupt(type: string | undefined): boolean {
  return (
    type === "checkpoint_chapter_1" ||
    type === "checkpoint_chapter_n" ||
    type === "checkpoint_remaining_batch"
  );
}
