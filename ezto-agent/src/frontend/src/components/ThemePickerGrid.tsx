import type { ThemeInfo } from "../api/client";

interface Props {
  themes: ThemeInfo[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Hide bestFor tags — use in compact popover */
  compact?: boolean;
  /** When set, only show these theme ids (plan checkpoint recommendations) */
  filterIds?: string[];
  loading?: boolean;
  applyingId?: string | null;
}

export default function ThemePickerGrid({
  themes,
  selectedId,
  onSelect,
  compact = false,
  filterIds,
  loading = false,
  applyingId = null,
}: Props) {
  if (loading) {
    return <p className="theme-picker-loading">加载主题中…</p>;
  }

  const visible = filterIds?.length
    ? themes.filter((t) => filterIds.includes(t.id))
    : themes;

  if (visible.length === 0) {
    return <p className="theme-picker-loading">暂无可用主题</p>;
  }

  return (
    <div className={`theme-grid${compact ? " theme-grid-compact" : ""}`}>
      {visible.map((theme) => {
        const selected = selectedId === theme.id;
        const applying = applyingId === theme.id;
        return (
          <button
            key={theme.id}
            type="button"
            className={`theme-card${selected ? " selected" : ""}${applying ? " applying" : ""}`}
            onClick={() => onSelect(theme.id)}
            disabled={Boolean(applyingId)}
            aria-pressed={selected}
            aria-label={`主题 ${theme.nameZh}`}
          >
            <div className="theme-preview">
              {theme.preview && (
                <div className="theme-swatches">
                  <span
                    className="swatch"
                    style={{ background: theme.preview.shell }}
                    aria-hidden
                  />
                  <span
                    className="swatch"
                    style={{ background: theme.preview.surface }}
                    aria-hidden
                  />
                  <span
                    className="swatch"
                    style={{ background: theme.preview.accent }}
                    aria-hidden
                  />
                </div>
              )}
            </div>
            <div className="theme-name">{theme.nameZh}</div>
            {!compact && (
              <>
                <div className="theme-desc">{theme.descriptionZh}</div>
                <div className="theme-tags">
                  {theme.bestFor.slice(0, 3).map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              </>
            )}
            {applying && <span className="theme-card-status">切换中…</span>}
          </button>
        );
      })}
    </div>
  );
}
