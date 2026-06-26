import type { ReactNode } from "react";

export interface SceneChromeProps {
  /** Masthead left label — series / product name */
  brand?: string;
  /** Masthead right metadata line (uppercase mono) */
  issue?: string;
  children: ReactNode;
  className?: string;
  /** Skip masthead + rule (rare full-bleed steps) */
  bare?: boolean;
}

/**
 * Standard scene wrapper: stage padding + masthead + rule + content grid.
 * Header and main share `.lx-stage-grid` for aligned margins.
 */
export function SceneChrome({
  brand = "Presentation",
  issue,
  children,
  className = "",
  bare = false,
}: SceneChromeProps) {
  return (
    <div className={`lx-scene scene-pad ${className}`.trim()}>
      {!bare && (
        <div className="lx-stage-grid lx-stage-header">
          <header className="masthead lx-masthead">
            <span className="brand">{brand}</span>
            {issue ? <span className="issue">{issue}</span> : null}
          </header>
          <hr className="rule lx-rule-gap" />
        </div>
      )}
      {bare ? (
        children
      ) : (
        <div className="lx-body-fill">
          <div className="lx-stage-grid lx-stage-main">{children}</div>
        </div>
      )}
    </div>
  );
}
