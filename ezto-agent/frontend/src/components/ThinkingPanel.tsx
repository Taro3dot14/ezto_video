import { useState, useRef, useEffect } from "react";

interface ThinkingEvent {
  type: string;
  content: string;
  ts: number;
}

interface Props {
  events: ThinkingEvent[];
}

const TYPE_ICONS: Record<string, string> = {
  node_start: "▶",
  node_end: "✓",
  node_error: "✗",
  step: "·",
  llm: "🤖",
  validation: "🔍",
  repair: "🔧",
  file_write: "📄",
};

const TYPE_LABELS: Record<string, string> = {
  node_start: "开始",
  node_end: "完成",
  node_error: "错误",
  step: "步骤",
  llm: "LLM",
  validation: "校验",
  repair: "修复",
  file_write: "文件",
};

export default function ThinkingPanel({ events }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevLenRef = useRef(0);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (events.length > prevLenRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      prevLenRef.current = events.length;
    }
  }, [events.length]);

  if (events.length === 0) return null;

  // Show last event as a compact "now" indicator when collapsed
  const lastEvent = events[events.length - 1];

  return (
    <div className="thinking-panel">
      <div className="tp-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="tp-toggle">{collapsed ? "▸" : "▾"}</span>
        <span className="tp-title">思考过程</span>
        <span className="tp-count">{events.length} 条</span>
        {collapsed && lastEvent && (
          <span className="tp-now">{lastEvent.content.slice(0, 40)}</span>
        )}
      </div>

      {!collapsed && (
        <div className="tp-body">
          {events.map((ev, i) => {
            const icon = TYPE_ICONS[ev.type] || "·";
            const label = TYPE_LABELS[ev.type] || ev.type;
            const isError = ev.type === "node_error";
            const isNodeStart = ev.type === "node_start";
            return (
              <div
                key={i}
                className={`tp-event ${isError ? "tp-error" : ""} ${isNodeStart ? "tp-node-start" : ""}`}
              >
                <span className="tp-icon">{icon}</span>
                <span className="tp-label">{label}</span>
                <span className="tp-text">{ev.content}</span>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
