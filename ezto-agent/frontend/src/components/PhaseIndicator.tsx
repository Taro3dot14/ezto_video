interface Props {
  currentPhase: string;
  completedNodes: string[];
}

const PHASES = [
  { id: "phase1", label: "Phase 1", desc: "内容编写" },
  { id: "phase2", label: "Phase 2", desc: "网页开发" },
  { id: "phase3", label: "Phase 3", desc: "音频合成" },
  { id: "phase4", label: "Phase 4", desc: "录屏 + 后期" },
];

export default function PhaseIndicator({ currentPhase, completedNodes }: Props) {
  const phaseOrder = ["phase1", "phase2", "phase3", "phase4"];
  const currentIdx = phaseOrder.indexOf(currentPhase);

  return (
    <div className="phase-indicator">
      <h4 className="pi-title">工作流阶段</h4>
      <div className="pi-list">
        {PHASES.map((p, i) => {
          const isActive = p.id === currentPhase;
          const isDone = phaseOrder.indexOf(p.id) < currentIdx;
          return (
            <div
              key={p.id}
              className={`pi-item ${isActive ? "active" : ""} ${isDone ? "done" : ""}`}
            >
              <span className="pi-dot" />
              <span className="pi-label">{p.label}</span>
              <span className="pi-desc">{p.desc}</span>
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
