import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getWorkflowState,
  resumeWorkflow,
  subscribeEvents,
  type WorkflowState,
  type ArtifactInfo,
} from "../api/client";
import CheckpointPlanView from "../components/CheckpointPlanView";
import ChapterReviewView from "../components/ChapterReviewView";
import CheckpointAudioView from "../components/CheckpointAudioView";
import ExecutionStream from "../components/ExecutionStream";
import WorkflowSidebar from "../components/WorkflowSidebar";
import LoadingState from "../components/LoadingState";

/* ── Plan milestones derived from workflow nodes ── */

interface Milestone {
  node: string;
  label: string;
}

const PLAN_MILESTONES: Milestone[] = [
  { node: "wv_identify_input", label: "Identify input" },
  { node: "wv_prepare_source_files", label: "Write script & outline" },
  { node: "wv_validate_script", label: "Validate script" },
  { node: "wv_repair_script", label: "Repair script issues" },
  { node: "wv_validate_outline", label: "Validate outline" },
  { node: "wv_repair_outline", label: "Repair outline issues" },
  { node: "wv_scaffold_presentation", label: "Scaffold presentation" },
  { node: "wv_remove_example_chapter", label: "Setup chapters" },
  { node: "wv_build_chapter_1", label: "Build chapter 1" },
  { node: "wv_build_chapter_n", label: "Build remaining chapters" },
  { node: "wv_extract_narrations", label: "Extract narrations" },
  { node: "wv_synthesize_audio", label: "Synthesize audio" },
  { node: "wv_recording_guidance", label: "Recording guidance" },
];

type StepStatus = "done" | "current" | "pending";

export default function WorkflowPage() {
  const { id: threadId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<WorkflowState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [thinkingEvents, setThinkingEvents] = useState<
    Record<string, unknown>[]
  >([]);

  const fetchState = useCallback(async () => {
    if (!threadId) return;
    try {
      const s = await getWorkflowState(threadId);
      setState(s);
      if (s.thinking_log && s.thinking_log.length > 0) {
        setThinkingEvents((prev) =>
          prev.length === 0 ? (s.thinking_log as any) : prev,
        );
      }
      setLoading(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "获取状态失败");
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  useEffect(() => {
    if (!threadId) return;
    const unsub = subscribeEvents(
      threadId,
      (event) => {
        if (event.type === "state_change" || event.completed_nodes) {
          fetchState();
        }
      },
      (events) => setThinkingEvents((prev) => [...prev, ...events]),
      () => fetchState(),
      (err) => setError(err.message),
    );
    return unsub;
  }, [threadId, fetchState]);

  const handleResume = async (confirmations: Record<string, unknown>) => {
    if (!threadId) return;
    setError(null);
    try {
      const res = await resumeWorkflow(threadId, confirmations);
      setState(res.state);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交确认失败");
    }
  };

  /* ── Derived data ── */
  const interrupt = state?.pending_interrupt;
  const interruptType = (interrupt?.type as string) || undefined;
  const completedNodes = state?.completed_nodes ?? [];
  const currentNode = state?.current_node ?? null;
  const artifacts: ArtifactInfo[] = state?.artifacts ?? [];

  const planSteps = useMemo(() => {
    return PLAN_MILESTONES.map((m) => {
      let st: StepStatus = "pending";
      if (completedNodes.includes(m.node)) st = "done";
      else if (currentNode === m.node) st = "current";
      else if (
        completedNodes.length > 0 &&
        !completedNodes.includes(m.node) &&
        PLAN_MILESTONES.findIndex(
          (x) => x.node === m.node,
        ) <
          PLAN_MILESTONES.findIndex(
            (x) => x.node === completedNodes[completedNodes.length - 1],
          )
      ) {
        st = "done";
      }
      return { ...m, status: st };
    });
  }, [completedNodes, currentNode]);

  /* ── Initial loading / error ── */
  if (loading) return <LoadingState message="加载工作流…" />;
  if (error) return <div className="error-box">{error}</div>;
  if (!state) return <div className="error-box">工作流未找到</div>;

  /* ── Done state ── */
  if (state.final_summary) {
    return (
      <div className="wf-done-page">
        <div className="wf-done-card">
          <h2>工作流完成</h2>
          <pre className="wf-done-summary">{state.final_summary}</pre>
          <button className="btn btn-primary" onClick={() => navigate("/")}>
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const isRunning = !interruptType;

  const topbarNodeLabel = currentNode
    ? currentNode.replace(/^wv_/, "")
    : "—";

  return (
    <div className="wf-shell">
      {/* ── Top Bar ── */}
      <header className="wf-topbar">
        <div className="wf-topbar-left">
          <span className="wf-topbar-title">Video Workflow</span>
          <span className="wf-topbar-divider" />
          <span className="wf-topbar-phase">{state.current_phase}</span>
        </div>
        <div className="wf-topbar-center">
          {isRunning && <span className="wf-topbar-dot" />}
          <span className="wf-topbar-node">{topbarNodeLabel}</span>
        </div>
        <div className="wf-topbar-right">
          <span className="wf-topbar-count">
            {completedNodes.length} nodes
          </span>
          <div className="wf-topbar-progress">
            <div
              className="wf-topbar-progress-fill"
              style={{
                width: `${Math.min((completedNodes.length / 34) * 100, 100)}%`,
              }}
            />
          </div>
        </div>
      </header>

      {/* ── Grid: Sidebar + Console ── */}
      <div className="wf-grid">
        <WorkflowSidebar
          currentPhase={state.current_phase}
          currentNode={currentNode}
          completedNodes={completedNodes}
          artifacts={artifacts}
        />

        <main className="wf-console">
          {/* Plan Summary */}
          <div className="wf-plan">
            <div className="wf-section-title">Plan</div>
            <div className="wf-plan-list">
              {planSteps.map((step, i) => (
                <div
                  key={i}
                  className={`wf-plan-step wf-plan-${step.status}`}
                >
                  <span className="wf-plan-icon">
                    {step.status === "done"
                      ? "✓"
                      : step.status === "current"
                        ? "●"
                        : "○"}
                  </span>
                  <span className="wf-plan-label">{step.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Execution Stream */}
          <ExecutionStream
            events={thinkingEvents as any}
            completedNodes={completedNodes}
            currentNode={currentNode}
            workflowActive={isRunning}
          />

          {/* Errors from state */}
          {state.errors && (state.errors as any[]).length > 0 && (
            <div className="wf-validation wf-validation-error">
              <div className="wf-section-title">Errors</div>
              <div className="wf-validation-list">
                {(state.errors as any[]).map((err: any, i: number) => (
                  <div key={i} className="wf-validation-item">
                    <span className="wf-validation-icon wf-err-icon">✗</span>
                    <span className="wf-validation-msg">
                      {err.error || err.message || JSON.stringify(err)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ── Bottom Status Bar ── */}
      <footer className="wf-bottombar">
        <div className="wf-bottombar-left">
          {isRunning && (
            <>
              <span className="wf-bottombar-dot" />
              <span className="wf-bottombar-status">Running</span>
            </>
          )}
          {interruptType && (
            <>
              <span className="wf-bottombar-dot wf-bottombar-waiting" />
              <span className="wf-bottombar-status">Awaiting input</span>
            </>
          )}
        </div>
        <div className="wf-bottombar-center">
          <span className="wf-bottombar-node">{topbarNodeLabel}</span>
        </div>
        <div className="wf-bottombar-right">
          <span className="wf-bottombar-info">
            {state.current_phase} · {completedNodes.length} / 34 nodes
          </span>
        </div>
      </footer>

      {/* ── Modal overlays (unchanged) ── */}
      {interruptType === "checkpoint_plan" && (
        <div className="modal-overlay">
          <div className="modal-card">
            <CheckpointPlanView
              interrupt={interrupt!}
              threadId={threadId!}
              onResume={handleResume}
            />
          </div>
        </div>
      )}
      {(interruptType === "checkpoint_chapter_1" ||
        interruptType === "checkpoint_chapter_n") && (
        <div className="modal-overlay">
          <div className="modal-card">
            <ChapterReviewView
              interrupt={interrupt!}
              threadId={threadId!}
              onResume={handleResume}
            />
          </div>
        </div>
      )}
      {interruptType === "checkpoint_remaining_batch" && (
        <div className="modal-overlay">
          <div className="modal-card">
            <ChapterReviewView
              interrupt={interrupt!}
              threadId={threadId!}
              onResume={handleResume}
            />
          </div>
        </div>
      )}
      {interruptType === "checkpoint_audio" && (
        <div className="modal-overlay">
          <div className="modal-card">
            <CheckpointAudioView
              interrupt={interrupt!}
              threadId={threadId!}
              onResume={handleResume}
            />
          </div>
        </div>
      )}
      {interruptType === "checkpoint_audio_segments" && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3>检查 audio-segments.json</h3>
            <p>路径：{String(interrupt?.path ?? "")}</p>
            <button
              className="btn btn-primary"
              onClick={() => handleResume({ approved: true })}
            >
              确认正确，继续合成
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
