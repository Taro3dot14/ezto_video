interface Props {
  expanded: boolean;
  onToggle: () => void;
  expandLabel: string;
  collapseLabel: string;
  controlsId: string;
  className?: string;
  /** vertical = up/down chevron; horizontal = left/right chevron (sidebars) */
  direction?: "vertical" | "horizontal";
  iconOnly?: boolean;
}

function ToggleIcon({
  expanded,
  direction,
}: {
  expanded: boolean;
  direction: "vertical" | "horizontal";
}) {
  const path =
    direction === "horizontal"
      ? expanded
        ? "M13 6l-4 4 4 4"
        : "M7 6l4 4-4 4"
      : "M6 8l4 4 4-4";

  return (
    <svg
      className={[
        "wf-panel-toggle-icon",
        direction === "vertical" && expanded ? "is-expanded" : "",
        direction === "horizontal" ? "is-horizontal" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      viewBox="0 0 20 20"
      aria-hidden
    >
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function PanelCollapseToggle({
  expanded,
  onToggle,
  expandLabel,
  collapseLabel,
  controlsId,
  className,
  direction = "vertical",
  iconOnly = false,
}: Props) {
  const label = expanded ? collapseLabel : expandLabel;

  return (
    <button
      type="button"
      className={[
        "wf-panel-toggle",
        iconOnly ? "wf-panel-toggle-icon-only" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={onToggle}
      aria-expanded={expanded}
      aria-controls={controlsId}
      aria-label={label}
      title={label}
    >
      {!iconOnly && <span className="wf-panel-toggle-text">{label}</span>}
      <ToggleIcon expanded={expanded} direction={direction} />
    </button>
  );
}
