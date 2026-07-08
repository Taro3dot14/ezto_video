import { useMemo, useState, useRef, useEffect, useCallback } from "react";
import { GROUP_LABELS, THINK_STAGE_COUNT, displayNodeLabel } from "../workflow/nodeCatalog";
import { useGroupTypewriter } from "../hooks/useGroupTypewriter";
import WorkflowPanelHeader from "./WorkflowPanelHeader";

export interface TraceEvent {
  type: string;
  content: string;
  ts: number;
  agent?: string;
}

export interface ExecutionStep {
  id: string;
  node_id: string;
  label: string;
  phase: string;
  status: "running" | "completed" | "failed";
  group?: string | null;
  started_at: number;
  ended_at?: number | null;
  events: TraceEvent[];
}

interface DisplayGroup {
  key: string;
  label: string;
  status: "running" | "completed" | "failed";
  steps: ExecutionStep[];
  started_at: number;
  ended_at?: number | null;
}

interface TodoItem {
  label: string;
  done: boolean;
}

interface TodoSnapshot {
  done: number;
  total: number;
  items: TodoItem[];
}

type CraftItemState = "pass" | "fail" | "pending" | "deferred";

interface CraftChecklistItem {
  index: number;
  id: string;
  label: string;
  state: CraftItemState;
  evidence?: string;
  mode?: string;
}

interface CraftChecklistSnapshot {
  done: number;
  total: number;
  review_ok: boolean;
  items: CraftChecklistItem[];
}

type TimelineStatus = "ok" | "fail" | "warn" | "neutral";

interface TimelineItem {
  id: string;
  kind: "phase" | "step" | "note" | "status";
  text: string;
  status?: TimelineStatus;
  eventType?: string;
  agent?: string;
}

interface Props {
  trace: ExecutionStep[];
  workflowActive: boolean;
}

const AGENT_META: Record<string, { label: string; className: string }> = {
  builder: { label: "Builder", className: "is-builder" },
  reviewer: { label: "Reviewer", className: "is-reviewer" },
  repair: { label: "Repair", className: "is-repair" },
  verify: { label: "Verify", className: "is-verify" },
  orchestrator: { label: "编排", className: "is-orchestrator" },
  team: { label: "Team", className: "is-team" },
  "team-plan": { label: "Team 方案", className: "is-team-plan" },
  "team-reviewer": { label: "Team · Reviewer", className: "is-team-reviewer" },
  "team-builder": { label: "Team · Builder", className: "is-team-builder" },
  "team-repair": { label: "Team · Repair", className: "is-team-repair" },
};

function resolveAgentMeta(agent?: string, content?: string): { label: string; className: string } | null {
  if (agent && AGENT_META[agent]) return AGENT_META[agent];

  const text = content ?? "";
  const teamRole = text.match(/^\[Team\/(\w+)\]/);
  if (teamRole) {
    const key = `team-${teamRole[1].toLowerCase()}`;
    if (AGENT_META[key]) return AGENT_META[key];
  }
  if (text.includes("Team Action Plan")) return AGENT_META["team-plan"];
  if (/Reviewer\s*子\s*Agent|Agent Team.*Reviewer/i.test(text)) return AGENT_META.reviewer;
  if (/Repair\s*子\s*Agent|Agent Team.*Repair/i.test(text)) return AGENT_META.repair;
  if (/Verify\s*阶段/i.test(text)) return AGENT_META.verify;
  if (/Agent Team.*Builder/i.test(text)) return AGENT_META.builder;
  if (/章节构建模式/i.test(text)) return AGENT_META.orchestrator;

  return null;
}

function AgentTag({ agent, content }: { agent?: string; content?: string }) {
  const meta = resolveAgentMeta(agent, content);
  if (!meta) return null;
  return (
    <span className={`wf-agent-tag ${meta.className}`} aria-label={`Agent: ${meta.label}`}>
      {meta.label}
    </span>
  );
}

const EVENT_HINTS: Record<string, string> = {
  step: "步骤",
  tool: "工具",
  validation: "核对",
  repair: "优化",
  file_write: "写入",
  error: "错误",
  agent: "页面",
};

interface ToolAuditPayload {
  tool: string;
  code: string;
  blocked: boolean;
  done: boolean;
  ms: number;
  chars: number;
}

function parseToolAudit(content: string): ToolAuditPayload | null {
  try {
    const data = JSON.parse(content) as ToolAuditPayload;
    if (!data || typeof data.tool !== "string") return null;
    return data;
  } catch {
    return null;
  }
}

function formatToolAuditLine(audit: ToolAuditPayload): { text: string; status: TimelineStatus } {
  const ms = audit.ms >= 10 ? `${Math.round(audit.ms)}ms` : "<10ms";
  const chars =
    audit.chars >= 1000 ? `${(audit.chars / 1000).toFixed(1)}k chars` : `${audit.chars} chars`;

  if (audit.done) {
    return { text: `${audit.tool} · 完成`, status: "ok" };
  }
  if (audit.blocked || audit.code === "blocked") {
    return { text: `${audit.tool} · 策略拦截`, status: "warn" };
  }
  if (audit.code === "parse") {
    return { text: `${audit.tool} · 参数解析失败`, status: "fail" };
  }
  if (audit.code === "exec") {
    return { text: `${audit.tool} · 执行错误`, status: "fail" };
  }
  if (audit.code === "not_found") {
    return { text: `${audit.tool} · 不可用`, status: "fail" };
  }
  return { text: `${audit.tool} · ${ms} · ${chars}`, status: "neutral" };
}

function isHiddenThinkEvent(ev: TraceEvent): boolean {
  if (/调用\s*DeepSeek/i.test(ev.content)) return true;
  if (/Agent\s*思考中/.test(ev.content)) return true;
  return false;
}

/** Soften legacy / harsh backend copy for the thinking panel. */
function softenThinkText(raw: string): { text: string; tone: TimelineStatus } {
  let t = raw.trim();

  const issueCount = t.match(/^[❌✅⚠️]?\s*发现\s*(\d+)\s*个?(?:问题|优化目标)/);
  if (issueCount) {
    return { text: `发现了 ${issueCount[1]} 个优化目标`, tone: "neutral" };
  }

  if (/口播稿风格核对通过|script\.md\s*校验通过/.test(t)) {
    return { text: "口播稿风格核对通过", tone: "ok" };
  }
  if (/大纲结构核对通过|outline\.md\s*校验通过/.test(t)) {
    return { text: "大纲结构核对通过", tone: "ok" };
  }

  if (/已达修复上限|本轮优化次数已用尽/.test(t)) {
    return { text: "本轮优化次数已用尽，继续后续流程", tone: "warn" };
  }

  if (/思考轮数超过\d+，思考中断/.test(t)) {
    return { text: t, tone: "warn" };
  }

  const repairRound = t.match(/^第\s*(\d+)\s*(?:次修复|轮优化)/);
  if (repairRound) {
    return { text: `第 ${repairRound[1]} 轮优化`, tone: "neutral" };
  }

  if (t.startsWith("✅")) return { text: t.replace(/^✅\s*/, ""), tone: "ok" };
  if (t.startsWith("⚠️")) return { text: t.replace(/^⚠️\s*/, ""), tone: "warn" };
  if (t.startsWith("❌")) return { text: t.replace(/^❌\s*/, ""), tone: "neutral" };

  return { text: t, tone: "neutral" };
}

function isNoteBullet(text: string): boolean {
  return /^\s*[•·]\s/.test(text) || (text.startsWith("•") && text.length > 1);
}

/** Merge consecutive steps in the same validation group into one card. */
function toDisplayGroups(trace: ExecutionStep[]): DisplayGroup[] {
  const groups: DisplayGroup[] = [];

  for (const step of trace) {
    const last = groups[groups.length - 1];
    if (step.group && last?.steps[0]?.group === step.group) {
      last.steps.push(step);
      if (step.status === "running") last.status = "running";
      else if (step.status === "failed") last.status = "failed";
      else if (last.status !== "running" && last.status !== "failed") {
        last.status = "completed";
      }
      if (step.ended_at) last.ended_at = step.ended_at;
      continue;
    }

    const groupKey = step.group;
    const label =
      groupKey && GROUP_LABELS[groupKey]
        ? GROUP_LABELS[groupKey]
        : displayNodeLabel(step.node_id) || step.label;

    groups.push({
      key: step.group ? `group:${step.group}` : step.id,
      label,
      status: step.status,
      steps: [step],
      started_at: step.started_at,
      ended_at: step.ended_at,
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

function isAgentStep(step: ExecutionStep): boolean {
  return step.node_id.includes("build_chapter");
}

function parseTodoContent(content: string): TodoSnapshot | null {
  const lines = content.split("\n");
  let done = 0;
  let total = 0;
  const items: TodoItem[] = [];

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;

    const header = line.match(/^✅\s*\[(\d+)\/(\d+)\]/);
    if (header) {
      done = Number(header[1]);
      total = Number(header[2]);
      continue;
    }

    const item = line.match(/^(✅|☐)\s+(.+)$/);
    if (item) {
      items.push({ label: item[2], done: item[1] === "✅" });
    }
  }

  if (items.length === 0) return null;
  if (total === 0) total = items.length;
  if (done === 0) done = items.filter((i) => i.done).length;

  return { done, total, items };
}

function parseCraftChecklistContent(content: string): CraftChecklistSnapshot | null {
  try {
    const data = JSON.parse(content) as CraftChecklistSnapshot;
    if (!data || !Array.isArray(data.items)) return null;
    return data;
  } catch {
    return null;
  }
}

function extractLatestCraftChecklist(events: TraceEvent[]): CraftChecklistSnapshot | null {
  let latest: CraftChecklistSnapshot | null = null;
  for (const ev of events) {
    if (ev.type !== "craft_checklist") continue;
    const parsed = parseCraftChecklistContent(ev.content);
    if (parsed) latest = parsed;
  }
  return latest;
}

function isBuildPhaseTodo(todo: TodoSnapshot): boolean {
  if (todo.items.length === 0) return false;
  const blob = todo.items.map((i) => i.label).join(" ");
  if (/Fix all reviewer/i.test(blob)) return false;
  if (
    todo.items.length <= 2 &&
    todo.items.every((i) => /typecheck|check_vite/i.test(i.label))
  ) {
    return false;
  }
  return true;
}

function extractLatestTodo(events: TraceEvent[]): TodoSnapshot | null {
  let latest: TodoSnapshot | null = null;

  for (const ev of events) {
    if (ev.type === "todo") {
      if (ev.content.includes("[Reviewer]")) continue;
      const parsed = parseTodoContent(ev.content);
      if (parsed && isBuildPhaseTodo(parsed)) latest = parsed;
      continue;
    }
    if (ev.type === "step" && (ev.content.includes("☐") || /✅\s*\[\d+\/\d+\]/.test(ev.content))) {
      if (ev.content.includes("[Reviewer]")) continue;
      const parsed = parseTodoContent(ev.content);
      if (parsed && isBuildPhaseTodo(parsed)) latest = parsed;
    }
  }

  return latest;
}

function isTodoNoise(text: string): boolean {
  if (/^⚡ todolist_/.test(text)) return true;
  if (/^⚡ \w+/.test(text)) return true;
  if (text.includes("Valid: NARRATIONS_TS")) return true;
  if (/^✅ [A-Z_]+:/.test(text)) return true;
  if (/✅\s*\[\d+\/\d+\]/.test(text) && text.includes("☐")) return true;
  if (/^✅\s*\[\d+\/\d+\]/.test(text) && /^\s*(✅|☐)\s/m.test(text)) return true;
  return false;
}


function buildTimeline(events: TraceEvent[]): TimelineItem[] {
  const seen = new Set<string>();
  const items: TimelineItem[] = [];

  for (const ev of events) {
    if (ev.type === "todo" || isHiddenThinkEvent(ev)) continue;
    const raw = ev.content.trim();
    if (!raw || seen.has(raw) || isTodoNoise(raw)) continue;
    seen.add(raw);
    const agent = ev.agent;

    if (ev.type === "phase") {
      items.push({
        id: `${ev.ts}:phase:${raw}`,
        kind: "phase",
        text: raw.replace(/^▸\s*/, ""),
        agent,
      });
      continue;
    }

    if (isNoteBullet(raw)) {
      const noteText = raw.replace(/^\s*[•·]\s*/, "");
      items.push({
        id: `${ev.ts}:note:${noteText}`,
        kind: "note",
        text: noteText,
        status: "neutral",
        agent,
      });
      continue;
    }

    if (ev.type === "tool") {
      const audit = parseToolAudit(raw);
      if (!audit) continue;
      const { text, status } = formatToolAuditLine(audit);
      const dedupeKey = `tool:${audit.tool}:${audit.code}:${audit.ms}:${audit.chars}`;
      if (seen.has(dedupeKey)) continue;
      seen.add(dedupeKey);
      items.push({
        id: `${ev.ts}:tool:${audit.tool}:${items.length}`,
        kind: "step",
        text,
        status,
        eventType: "tool",
        agent,
      });
      continue;
    }

    if (ev.type === "validation" || ev.type === "repair") {
      const { text, tone } = softenThinkText(raw);
      items.push({
        id: `${ev.ts}:status:${text}`,
        kind: "status",
        text,
        status: tone,
        eventType: ev.type,
        agent,
      });
      continue;
    }

    if (ev.type === "llm") {
      items.push({
        id: `${ev.ts}:llm:${raw}`,
        kind: "step",
        text: raw,
        eventType: "llm",
        agent,
      });
      continue;
    }

    const { text } = softenThinkText(raw);
    items.push({
      id: `${ev.ts}:step:${text}`,
      kind: "step",
      text,
      eventType: ev.type,
      agent,
    });
  }

  return items;
}

function cycleSummary(events: TraceEvent[]): string {
  const repairs = events.filter(
    (e) => e.type === "repair" && /第\s*\d+\s*(次修复|轮优化)/.test(e.content),
  );
  const lastVal = [...events].reverse().find((e) => e.type === "validation");
  const parts: string[] = [];
  if (repairs.length > 0) parts.push(`${repairs.length} 轮优化`);
  if (lastVal) {
    const { text, tone } = softenThinkText(lastVal.content);
    if (tone === "ok" || text.includes("核对通过")) parts.push("已就绪");
    else if (text.includes("优化目标")) parts.push("有待优化项");
    else if (tone === "warn") parts.push("继续后续");
  }
  return parts.join(" · ") || "已完成";
}

type ChecklistBoxState = "empty" | "done" | "pass" | "fail" | "pending" | "deferred";

function ChecklistCheckbox({ state }: { state: ChecklistBoxState }) {
  return (
    <span className={`wf-exec-checklist-check is-${state}`} aria-hidden="true">
      {(state === "done" || state === "pass") && (
        <svg viewBox="0 0 12 12" width="10" height="10">
          <path
            d="M2 6l3 3 5-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {state === "fail" && (
        <svg viewBox="0 0 12 12" width="10" height="10">
          <path
            d="M3 3l6 6M9 3L3 9"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
      )}
      {state === "deferred" && <span className="wf-exec-checklist-check-deferred">…</span>}
    </span>
  );
}

function CraftChecklistPanel({ craft }: { craft: CraftChecklistSnapshot }) {
  const pct = craft.total > 0 ? Math.round((craft.done / craft.total) * 100) : 0;
  const visibleItems = craft.items.filter((i) => i.mode !== "deferred" || i.state !== "deferred");

  return (
    <div className="wf-exec-checklist wf-exec-checklist--review">
      <div className="wf-exec-checklist-head">
        <span className="wf-exec-checklist-title">完工自检</span>
        <span className={`wf-exec-checklist-progress is-review${craft.review_ok ? " is-ok" : ""}`}>
          {craft.done}/{craft.total}
        </span>
      </div>
      <div className="wf-exec-checklist-bar is-review" aria-hidden="true">
        <span className="wf-exec-checklist-bar-fill is-review" style={{ width: `${pct}%` }} />
      </div>
      <div className="wf-exec-checklist-scroll wf-clay-scroll">
        <ul className="wf-exec-checklist-list">
          {visibleItems.map((item) => (
            <li
              key={item.id}
              className={`wf-exec-checklist-item is-${item.state}`}
            >
              <ChecklistCheckbox state={item.state} />
              <span className="wf-exec-checklist-item-body">
                <span className="wf-exec-checklist-label">
                  <span className="wf-exec-checklist-num">{String(item.index).padStart(2, "0")}</span>
                  {item.label}
                </span>
                {item.state === "fail" && item.evidence ? (
                  <span className="wf-exec-checklist-evidence">{item.evidence}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function TodoPanel({ todo }: { todo: TodoSnapshot }) {
  const pct = todo.total > 0 ? Math.round((todo.done / todo.total) * 100) : 0;

  return (
    <div className="wf-exec-checklist wf-exec-checklist--build">
      <div className="wf-exec-checklist-head">
        <span className="wf-exec-checklist-title">构建清单</span>
        <span className="wf-exec-checklist-progress is-build">
          {todo.done}/{todo.total}
        </span>
      </div>
      <div className="wf-exec-checklist-bar is-build" aria-hidden="true">
        <span className="wf-exec-checklist-bar-fill is-build" style={{ width: `${pct}%` }} />
      </div>
      <div className="wf-exec-checklist-scroll wf-clay-scroll">
        <ul className="wf-exec-checklist-list">
          {todo.items.map((item, i) => (
            <li
              key={`${item.label}-${i}`}
              className={`wf-exec-checklist-item${item.done ? " is-done" : ""}`}
            >
              <ChecklistCheckbox state={item.done ? "done" : "empty"} />
              <span className="wf-exec-checklist-item-body">
                <span className="wf-exec-checklist-label">{item.label}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ChecklistPanelsRow({
  build,
  review,
}: {
  build: TodoSnapshot | null;
  review: CraftChecklistSnapshot | null;
}) {
  if (!build && !review) return null;

  const showBuild = Boolean(build) && !review;

  return (
    <div
      className={`wf-exec-checklists${review ? " is-review-only" : ""}`}
      role="group"
      aria-label={review ? "完工自检进度" : "章节构建进度"}
    >
      {showBuild && <TodoPanel todo={build!} />}
      {review && <CraftChecklistPanel craft={review} />}
    </div>
  );
}

function ThinkTimeline({
  items,
  running,
  animate,
  onStreamTick,
}: {
  items: TimelineItem[];
  running: boolean;
  animate: boolean;
  onStreamTick?: () => void;
}) {
  const { displayText, isTyping, isItemVisible, isStreaming, revision } = useGroupTypewriter(
    items,
    { animate },
  );

  useEffect(() => {
    if (animate && revision > 0) onStreamTick?.();
  }, [revision, animate, onStreamTick]);

  if (items.length === 0) return null;

  return (
    <div className={`wf-think-timeline${running || isStreaming ? " is-live" : ""}`}>
      {items.map((item, i) => {
        if (!isItemVisible(i)) return null;

        const typing = isTyping(item, i);
        const shown = displayText(item);

        if (item.kind === "phase") {
          return (
            <div key={item.id} className="wf-think-phase">
              {shown}
              {typing && <span className="wf-think-cursor" aria-hidden="true" />}
            </div>
          );
        }

        if (item.kind === "note") {
          return (
            <div key={item.id} className="wf-think-note">
              {shown}
              {typing && <span className="wf-think-cursor" aria-hidden="true" />}
            </div>
          );
        }

        if (item.kind === "status") {
          return (
            <div
              key={item.id}
              className={`wf-think-status is-${item.status ?? "neutral"}${typing ? " is-live" : ""}`}
            >
              <AgentTag agent={item.agent} content={item.text} />
              <span className="wf-think-status-text">
                {shown}
                {typing && <span className="wf-think-cursor" aria-hidden="true" />}
              </span>
            </div>
          );
        }

        return (
          <div
            key={item.id}
            className={`wf-think-step${typing ? " is-live" : ""}${
              item.eventType === "tool" ? " is-tool" : ""
            }${item.status === "warn" ? " is-blocked" : ""}${
              item.status === "fail" ? " is-fail" : ""
            }${item.status === "ok" ? " is-ok" : ""}`}
          >
            <AgentTag agent={item.agent} content={item.text} />
            {item.eventType && item.eventType !== "step" && item.eventType !== "llm" && (
              <span className="wf-think-tag">{EVENT_HINTS[item.eventType] ?? item.eventType}</span>
            )}
            <span className="wf-think-step-text">
              {shown}
              {typing && <span className="wf-think-cursor" aria-hidden="true" />}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const SCROLL_PIN_THRESHOLD = 48;

function isScrollPinnedToBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_PIN_THRESHOLD;
}

export default function ExecutionStream({ trace, workflowActive }: Props) {
  const groups = useMemo(() => toDisplayGroups(trace), [trace]);
  const [panelExpanded, setPanelExpanded] = useState(true);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const scrollContainerRef = useRef<HTMLElement | null>(null);
  const pinnedToBottomRef = useRef(true);
  const prevGroupCount = useRef(0);

  useEffect(() => {
    scrollContainerRef.current = document.querySelector<HTMLElement>(".wf-console");
  }, []);

  const toggle = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  useEffect(() => {
    if (groups.length > prevGroupCount.current) {
      setCollapsed((prev) => {
        const next = new Set(prev);
        for (let i = 0; i < groups.length - 1; i++) {
          const g = groups[i];
          if (g.status === "completed") next.add(g.key);
        }
        return next;
      });
    }
    prevGroupCount.current = groups.length;
  }, [groups]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      pinnedToBottomRef.current = isScrollPinnedToBottom(el);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el || !pinnedToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [groups, scrollToBottom]);

  const hasRunning =
    groups.some((g) => g.status === "running") || workflowActive;

  const doneGroupCount = groups.filter((g) => g.status === "completed").length;
  const runningGroup = groups.find((g) => g.status === "running");
  const activeGroupCount = Math.min(
    doneGroupCount + (runningGroup ? 1 : 0),
    THINK_STAGE_COUNT,
  );
  const thinkSubtitle = runningGroup
    ? `进行中 · ${runningGroup.label}`
    : groups.length > 0 && doneGroupCount === groups.length
      ? "全部完成"
      : workflowActive
        ? "运行中…"
        : groups.length === 0
          ? "等待执行开始…"
          : "等待下一步";

  const thinkHeader = (
    <WorkflowPanelHeader
      variant="think"
      title="思考"
      kicker="实时记录"
      subtitle={thinkSubtitle}
      metaActive={activeGroupCount}
      metaTotal={THINK_STAGE_COUNT}
      metaLabel="环节"
      expanded={panelExpanded}
      onToggle={() => setPanelExpanded((v) => !v)}
      expandLabel="展开完整思考"
      collapseLabel="收起完整思考"
      controlsId="wf-think-body"
    />
  );

  if (groups.length === 0) {
    return (
      <section
        className={`wf-panel-card wf-execution${panelExpanded ? " is-expanded" : " is-collapsed"}`}
        aria-label="工作流思考"
      >
        {thinkHeader}
        <div id="wf-think-body" className="wf-panel-body">
          <div className="wf-panel-body-inner">
            <div className="wf-exec-scroll">
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
        </div>
      </section>
    );
  }

  return (
    <section
      className={`wf-panel-card wf-execution${panelExpanded ? " is-expanded" : " is-collapsed"}`}
      aria-label="工作流思考"
    >
      {thinkHeader}
      <div id="wf-think-body" className="wf-panel-body">
        <div className="wf-panel-body-inner">
          <div className="wf-exec-scroll">
        <div className="wf-exec-list">
          {groups.map((g) => {
            const running = g.status === "running";
            const fold = collapsed.has(g.key);
            const events = g.steps.flatMap((s) => s.events);
            const timeline = buildTimeline(events);
            const craft = extractLatestCraftChecklist(events);
            const todo = extractLatestTodo(events);
            const hasBody = timeline.length > 0 || !!todo || !!craft;
            const canFold = g.status === "completed" && hasBody;
            const agent = g.steps.some(isAgentStep);
            const isCycle = Boolean(g.steps[0]?.group);
            const duration =
              g.ended_at && g.started_at
                ? formatDuration((g.ended_at - g.started_at) * 1000)
                : "";
            const summary = isCycle && fold ? cycleSummary(events) : "";

            return (
              <div
                key={g.key}
                className={`wf-exec-node${running ? " is-running" : ""}${
                  g.status === "failed" ? " is-failed" : ""
                }${agent ? " is-agent" : ""}${isCycle ? " is-cycle" : ""}${
                  todo || craft ? " has-todo" : ""
                }${fold ? " is-folded" : ""}`}
              >
                <div
                  className="wf-exec-header"
                  onClick={() => canFold && toggle(g.key)}
                  style={canFold ? { cursor: "pointer" } : undefined}
                >
                  <span className="wf-exec-icon">
                    {running ? (
                      <span className="wf-think-pulse" aria-hidden="true" />
                    ) : g.status === "failed" ? (
                      "✗"
                    ) : (
                      "✓"
                    )}
                  </span>
                  <span className="wf-exec-name">{g.label}</span>
                  {fold && summary && (
                    <span className="wf-exec-summary">{summary}</span>
                  )}
                  <span className="wf-exec-duration">{duration}</span>
                  {canFold && (
                    <span className="wf-exec-arrow">{fold ? "▸" : "▾"}</span>
                  )}
                </div>
                {!fold && hasBody && (
                  <div className="wf-exec-body">
                    {timeline.length > 0 && (
                      <ThinkTimeline
                        items={timeline}
                        running={running}
                        animate={running && !fold}
                        onStreamTick={scrollToBottom}
                      />
                    )}
                    {(todo || craft) && (
                      <ChecklistPanelsRow build={todo} review={craft} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {hasRunning && (
          <div className="wf-exec-loading">
            <span className="wf-exec-loading-dot" />
            <span className="wf-exec-loading-dot" />
            <span className="wf-exec-loading-dot" />
          </div>
        )}
          </div>
        </div>
      </div>
    </section>
  );
}
