import type { ReactNode } from "react";

export type GridSlotState = "ghost" | "active" | "past";

export interface GridSlotProps {
  /** ghost = not yet revealed · active = current step · past = dimmed context */
  state: GridSlotState;
  /** Slot index label (e.g. "01" or "1") */
  num: string;
  title: ReactNode;
  body?: ReactNode;
  /** Optional demo content below title/body */
  children?: ReactNode;
  className?: string;
}

/**
 * One cell in lx-grid-3 list-reveal pattern.
 * Use one active slot per step; keep past slots visible as context.
 */
export function GridSlot({
  state,
  num,
  title,
  body,
  children,
  className = "",
}: GridSlotProps) {
  return (
    <div className={`lx-slot lx-slot-${state} ${className}`.trim()}>
      <div className="lx-slot-num">{num}</div>
      <div className="lx-slot-content">
        <div className="lx-slot-title">{title}</div>
        {body ? <div className="lx-slot-body">{body}</div> : null}
        {children}
      </div>
    </div>
  );
}

export interface ListGridProps {
  children: ReactNode;
  className?: string;
}

/** Wrapper for 3-column list-reveal grids. */
export function ListGrid({ children, className = "" }: ListGridProps) {
  return <div className={`lx-grid-3 ${className}`.trim()}>{children}</div>;
}
