import type { ArtifactInfo } from "../api/client";

interface Props {
  currentPhase: string;
  currentNode: string | null;
  completedNodes: string[];
  artifacts: ArtifactInfo[];
}

/* ── Phase data ── */

const PHASES = [
  { key: "phase1", label: "内容编写", en: "Phase 1" },
  { key: "phase2", label: "网页开发", en: "Phase 2" },
  { key: "phase3", label: "音频合成", en: "Phase 3" },
  { key: "phase4", label: "录屏 + 后期", en: "Phase 4" },
];

function phaseStatus(
  key: string,
  current: string,
  completedNodes: string[],
): "active" | "done" | "pending" {
  if (key === current) return "active";
  const order = PHASES.map((p) => p.key);
  const curIdx = order.indexOf(current);
  const thisIdx = order.indexOf(key);
  if (thisIdx < curIdx) return "done";
  // Check if all nodes up to this phase boundary are completed
  if (thisIdx < curIdx) return "done";
  return "pending";
}

/* ── Helpers ── */

function fmtSize(bytes: number | null): string {
  if (!bytes || bytes === 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function WorkflowSidebar({
  currentPhase,
  currentNode,
  completedNodes,
  artifacts,
}: Props) {
  const generated = artifacts.filter((a) => a.exists);
  const pending = artifacts.filter((a) => !a.exists);
  const completedCount = completedNodes.length;

  return (
    <div className="wf-sidebar">
      {/* ── Session ── */}
      <div className="wf-sidebar-section">
        <div className="wf-section-title">Session</div>
        <div className="wf-session-grid">
          <div className="wf-session-row">
            <span className="wf-session-label">Status</span>
            <span className="wf-session-value wf-status-running">Running</span>
          </div>
          <div className="wf-session-row">
            <span className="wf-session-label">Phase</span>
            <span className="wf-session-value">{currentPhase}</span>
          </div>
          <div className="wf-session-row">
            <span className="wf-session-label">Current</span>
            <span className="wf-session-value wf-session-mono">
              {currentNode || "—"}
            </span>
          </div>
          <div className="wf-session-row">
            <span className="wf-session-label">Completed</span>
            <span className="wf-session-value">{completedCount}</span>
          </div>
        </div>
      </div>

      {/* ── Phases ── */}
      <div className="wf-sidebar-section">
        <div className="wf-section-title">Phases</div>
        <div className="wf-phase-list">
          {PHASES.map((p) => {
            const st = phaseStatus(p.key, currentPhase, completedNodes);
            return (
              <div
                key={p.key}
                className={`wf-phase-item wf-phase-${st}`}
              >
                <span className="wf-phase-dot" />
                <span className="wf-phase-en">{p.en}</span>
                <span className="wf-phase-label">{p.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Files ── */}
      <div className="wf-sidebar-section">
        <div className="wf-section-title">Files</div>
        {generated.length > 0 && (
          <div className="wf-file-group">
            <div className="wf-file-group-title">generated</div>
            {generated.map((a) => (
              <div key={a.logical_name} className="wf-file-item">
                <span className="wf-file-icon">✓</span>
                <span className="wf-file-name">{a.path.split("/").pop()}</span>
                <span className="wf-file-size">{fmtSize(a.size)}</span>
              </div>
            ))}
          </div>
        )}
        {pending.length > 0 && (
          <div className="wf-file-group">
            <div className="wf-file-group-title">pending</div>
            {pending.map((a) => (
              <div key={a.logical_name} className="wf-file-item">
                <span className="wf-file-icon wf-file-pending">○</span>
                <span className="wf-file-name wf-file-dim">
                  {a.path.split("/").pop()}
                </span>
                <span className="wf-file-size" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Node History ── */}
      <div className="wf-sidebar-section">
        <div className="wf-section-title">Node History</div>
        <div className="wf-node-history">
          {completedNodes.length === 0 && !currentNode && (
            <div className="wf-history-empty">No nodes yet</div>
          )}
          {completedNodes.map((node, i) => (
            <div key={i} className="wf-history-item wf-history-done">
              <span className="wf-history-icon">✓</span>
              <span className="wf-history-name">{node}</span>
            </div>
          ))}
          {currentNode && (
            <div className="wf-history-item wf-history-current">
              <span className="wf-history-icon">●</span>
              <span className="wf-history-name">{currentNode}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
