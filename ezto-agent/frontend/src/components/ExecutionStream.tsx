import { useMemo, useState, useRef, useEffect } from "react";

interface ThinkingEvent {
  type: string;
  content: string;
  ts: number;
}

interface EventGroup {
  nodeName: string;
  status: "completed" | "running" | "failed";
  events: ThinkingEvent[];
  startTs: number;
  endTs?: number;
}

interface Props {
  events: ThinkingEvent[];
  completedNodes: string[];
  currentNode: string | null;
  workflowActive: boolean;
}

const EVENT_ICONS: Record<string, string> = {
  step: "·",
  llm: "↳",
  validation: "⚠",
  repair: "🔧",
  file_write: "✚",
};

function groupEvents(
  events: ThinkingEvent[],
  completedNodes: string[],
  currentNode: string | null,
): EventGroup[] {
  const groups: EventGroup[] = [];
  let current: EventGroup | null = null;

  for (const ev of events) {
    if (ev.type === "node_start") {
      if (current) {
        if (completedNodes.includes(current.nodeName))
          current.status = "completed";
        groups.push(current);
      }
      current = {
        nodeName: ev.content,
        status: "running",
        events: [],
        startTs: ev.ts,
      };
    } else if (ev.type === "node_end") {
      if (current) {
        current.status = "completed";
        current.endTs = ev.ts;
      }
    } else if (ev.type === "node_error") {
      if (current) {
        current.status = "failed";
        current.endTs = ev.ts;
      }
    } else {
      current?.events.push(ev);
    }
  }

  if (current) {
    if (completedNodes.includes(current.nodeName))
      current.status = "completed";
    groups.push(current);
  }

  for (const node of completedNodes) {
    if (!groups.find((g) => g.nodeName === node)) {
      groups.push({
        nodeName: node,
        status: "completed",
        events: [],
        startTs: 0,
      });
    }
  }

  if (
    currentNode &&
    !groups.find((g) => g.nodeName === currentNode)
  ) {
    groups.push({
      nodeName: currentNode,
      status: "running",
      events: [],
      startTs: Date.now(),
    });
  }

  return groups;
}

function formatDuration(ms: number): string {
  if (!ms || ms < 100) return "<1s";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function ExecutionStream({
  events,
  completedNodes,
  currentNode,
  workflowActive,
}: Props) {
  const groups = useMemo(
    () => groupEvents(events, completedNodes, currentNode),
    [events, completedNodes, currentNode],
  );
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const runningRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const toggle = (name: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [groups]);

  const hasRunning = groups.some((g) => g.status === "running") || workflowActive;

  if (groups.length === 0) {
    return (
      <div className="wf-execution">
        <div className="wf-exec-header-row">
          <span className="wf-section-title">思考过程</span>
        </div>
        <div className="wf-exec-scroll" ref={scrollRef}>
          <div className="wf-exec-empty">
            {workflowActive ? "运行中…" : "等待执行开始…"}
          </div>
          {workflowActive && (
            <div className="wf-exec-loading">
              <span className="wf-exec-loading-dot" />
              <span className="wf-exec-loading-dot" />
              <span className="wf-exec-loading-dot" />
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="wf-execution">
      <div className="wf-exec-header-row">
        <span className="wf-section-title">思考过程</span>
      </div>
      <div className="wf-exec-scroll" ref={scrollRef}>
        <div className="wf-exec-list">
          {groups.map((g, i) => {
            const running = g.status === "running";
            const fold = collapsed.has(g.nodeName);
            const canFold =
              g.status === "completed" && g.events.length > 0;

            return (
              <div
                key={i}
                ref={running ? runningRef : undefined}
                className={`wf-exec-node${running ? " is-running" : ""}${g.status === "failed" ? " is-failed" : ""}`}
              >
                <div
                  className="wf-exec-header"
                  onClick={() => canFold && toggle(g.nodeName)}
                  style={canFold ? { cursor: "pointer" } : undefined}
                >
                  <span className="wf-exec-icon">
                    {running ? "●" : g.status === "failed" ? "✗" : "▾"}
                  </span>
                  <span className="wf-exec-name">{g.nodeName}</span>
                  <span className="wf-exec-duration">
                    {g.status === "completed" && g.endTs
                      ? formatDuration(g.endTs - g.startTs)
                      : ""}
                  </span>
                  <span className="wf-exec-label">
                    {running
                      ? "running"
                      : g.status === "failed"
                        ? "failed"
                        : "completed"}
                  </span>
                  {canFold && (
                    <span className="wf-exec-arrow">{fold ? "▸" : "▾"}</span>
                  )}
                </div>
                {!fold && g.events.length > 0 && (
                  <div className="wf-exec-events">
                    {g.events.map((ev, j) => (
                      <div key={j} className="wf-exec-event">
                        <span className="wf-exec-ev-icon">
                          {EVENT_ICONS[ev.type] || "·"}
                        </span>
                        <span className="wf-exec-ev-text">{ev.content}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Loading animation at bottom when running */}
        {hasRunning && (
          <div className="wf-exec-loading">
            <span className="wf-exec-loading-dot" />
            <span className="wf-exec-loading-dot" />
            <span className="wf-exec-loading-dot" />
          </div>
        )}
      </div>
    </div>
  );
}
