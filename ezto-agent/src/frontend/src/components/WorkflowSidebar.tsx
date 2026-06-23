import type { ArtifactInfo, TokenUsage } from "../api/client";
import { displayNodeLabel } from "../workflow/nodeCatalog";

interface Props {
  completedNodes: string[];
  currentNode: string | null;
  artifacts: ArtifactInfo[];
  tokenUsage?: TokenUsage;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function fmtSize(bytes: number | null): string {
  if (!bytes || bytes === 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function WorkflowSidebar({
  completedNodes,
  currentNode,
  artifacts,
  tokenUsage,
}: Props) {
  const generated = artifacts.filter((a) => a.exists);
  const pending = artifacts.filter((a) => !a.exists);
  const modelRows = Object.entries(tokenUsage?.by_model ?? {}).sort(
    (a, b) => b[1].total_tokens - a[1].total_tokens,
  );
  const total = tokenUsage?.total;
  const maxTokens = modelRows[0]?.[1].total_tokens ?? 0;

  return (
    <div className="wf-sidebar">
      <div className="wf-sidebar-section">
        <div className="wf-section-title wf-section-title-row">
          <span>Token 用量</span>
          {total && total.total_tokens > 0 && (
            <span className="wf-token-header-total">
              {fmtTokens(total.total_tokens)}
            </span>
          )}
        </div>
        {modelRows.length === 0 ? (
          <div className="wf-token-empty">暂无消耗</div>
        ) : (
          <div className="wf-token-card">
            <ul className="wf-token-list" role="list">
              {modelRows.map(([model, stats]) => {
                const share =
                  maxTokens > 0
                    ? Math.round((stats.total_tokens / maxTokens) * 100)
                    : 0;
                return (
                  <li key={model} className="wf-token-item">
                    <div className="wf-token-item-head">
                      <span className="wf-token-model" title={model}>
                        {model}
                      </span>
                      <span className="wf-token-amount">
                        {fmtTokens(stats.total_tokens)}
                      </span>
                    </div>
                    <div
                      className="wf-token-bar"
                      role="presentation"
                      aria-hidden="true"
                    >
                      <span
                        className="wf-token-bar-fill"
                        style={{ width: `${share}%` }}
                      />
                    </div>
                    <div className="wf-token-meta">
                      {stats.calls} 次调用
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>

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

      <div className="wf-sidebar-section">
        <div className="wf-section-title">Node History</div>
        <div className="wf-node-history">
          {completedNodes.length === 0 && !currentNode && (
            <div className="wf-history-empty">No nodes yet</div>
          )}
          {completedNodes.map((node, i) => (
            <div key={i} className="wf-history-item wf-history-done">
              <span className="wf-history-icon">✓</span>
              <span className="wf-history-name">{displayNodeLabel(node)}</span>
            </div>
          ))}
          {currentNode && (
            <div className="wf-history-item wf-history-current">
              <span className="wf-history-icon">●</span>
              <span className="wf-history-name">{displayNodeLabel(currentNode)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
