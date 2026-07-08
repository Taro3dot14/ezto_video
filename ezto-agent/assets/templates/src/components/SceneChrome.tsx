import type { ReactNode } from "react";

export interface SceneChromeProps {
  children: ReactNode;
  className?: string;
}

/**
 * Standard scene wrapper: stage padding + content grid.
 * No masthead / page header — video stage is content-only (progress bar is hover-only in App).
 */
export function SceneChrome({ children, className = "" }: SceneChromeProps) {
  return (
    <div className={`lx-scene scene-pad ${className}`.trim()}>
      <div className="lx-body-fill">
        <div className="lx-stage-grid lx-stage-main">{children}</div>
      </div>
    </div>
  );
}
