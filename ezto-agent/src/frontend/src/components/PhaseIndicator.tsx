import { displayPhaseLabel } from "../workflow/nodeCatalog";

interface Props {
  currentPhase: string;
  completedNodes: string[];
}

const PHASE_IDS = ["phase1", "phase2", "phase3", "phase4"] as const;

export default function PhaseIndicator({ currentPhase, completedNodes }: Props) {
  const phaseOrder = ["phase1", "phase2", "phase3", "phase4"];
  const currentIdx = phaseOrder.indexOf(currentPhase);

  return (
    <div className="phase-indicator">
      <h4 className="pi-title">工作流阶段</h4>
      <div className="pi-list">
        {PHASE_IDS.map((id) => {
          const isActive = id === currentPhase;
          const isDone = phaseOrder.indexOf(id) < currentIdx;
          return (
            <div
              key={id}
              className={`pi-item ${isActive ? "active" : ""} ${isDone ? "done" : ""}`}
            >
              <span className="pi-dot" />
              <span className="pi-label">{displayPhaseLabel(id)}</span>
            </div>
          );
        })}
      </div>
      <div className="pi-stats">
        <span className="pi-count">
          已完成 {completedNodes.length} 个节点
        </span>
      </div>
    </div>
  );
}
