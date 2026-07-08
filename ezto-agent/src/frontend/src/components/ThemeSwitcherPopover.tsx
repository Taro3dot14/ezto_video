import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyProjectTheme,
  applyWorkflowTheme,
  listThemes,
  type ThemeInfo,
} from "../api/client";
import ThemePickerGrid from "./ThemePickerGrid";

interface Props {
  /** Active workflow thread id */
  threadId?: string;
  /** Project id when not on workflow page */
  projectId?: string;
  selectedTheme: string | null;
  visible: boolean;
  onThemeApplied: (themeId: string) => void;
  /** Inline button for project page; default floating FAB */
  inline?: boolean;
}

export default function ThemeSwitcherPopover({
  threadId,
  projectId,
  selectedTheme,
  visible,
  onThemeApplied,
  inline = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!visible) {
      setOpen(false);
      return;
    }
    setLoading(true);
    listThemes()
      .then(setThemes)
      .catch(() => setError("无法加载主题列表"))
      .finally(() => setLoading(false));
  }, [visible]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (
        panelRef.current?.contains(t) ||
        triggerRef.current?.contains(t)
      ) {
        return;
      }
      setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(t);
  }, [toast]);

  const handleSelect = useCallback(
    async (themeId: string) => {
      if (themeId === selectedTheme) {
        setOpen(false);
        return;
      }
      setError(null);
      setApplyingId(themeId);
      try {
        if (threadId) {
          await applyWorkflowTheme(threadId, themeId);
        } else if (projectId) {
          await applyProjectTheme(projectId, themeId);
        } else {
          throw new Error("缺少项目上下文");
        }
        const label = themes.find((t) => t.id === themeId)?.nameZh ?? themeId;
        onThemeApplied(themeId);
        setToast(`已切换为 ${label} — 请重新打开或刷新预览页`);
        setOpen(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "切换失败");
      } finally {
        setApplyingId(null);
      }
    },
    [threadId, projectId, selectedTheme, themes, onThemeApplied],
  );

  if (!visible) return null;

  return (
    <div
      className={inline ? "project-theme-switcher" : "wf-theme-switcher"}
      ref={panelRef}
    >
      {toast && (
        <div className="wf-theme-toast" role="status">
          {toast}
        </div>
      )}
      {open && (
        <div
          className={`wf-theme-panel wf-clay-scroll${inline ? " is-inline" : ""}`}
          role="dialog"
          aria-label="选择演示主题"
        >
          <div className="wf-theme-panel-head">
            <h4>切换主题</h4>
            <p>仅更换配色与字体 token，不重跑构建。刷新预览页查看效果。</p>
          </div>
          {error && <p className="wf-theme-error">{error}</p>}
          <ThemePickerGrid
            themes={themes}
            selectedId={selectedTheme}
            onSelect={handleSelect}
            compact
            loading={loading}
            applyingId={applyingId}
          />
        </div>
      )}
      <button
        ref={triggerRef}
        type="button"
        className={
          inline ? "btn btn-secondary project-theme-trigger" : "wf-preview-fab wf-theme-fab"
        }
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        title="切换演示主题"
      >
        {!inline && (
          <>
            <span className="wf-preview-fab-icon wf-theme-fab-icon" aria-hidden>
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
                <path
                  d="M12 3c-4 0-7 2.5-7 6s3 6 7 6 7-2.5 7-6-3-6-7-6Z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                />
                <path
                  d="M5 15c1.5 2.5 4 4 7 4s5.5-1.5 7-4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <circle cx="8" cy="8" r="1.2" fill="currentColor" />
                <circle cx="12" cy="7" r="1.2" fill="currentColor" />
                <circle cx="16" cy="9" r="1.2" fill="currentColor" />
              </svg>
            </span>
            <span className="wf-preview-fab-text">
              <span className="wf-preview-fab-label">主题</span>
              <span className="wf-preview-fab-hint">23 套风格</span>
            </span>
          </>
        )}
        {inline && "切换演示主题"}
      </button>
    </div>
  );
}
