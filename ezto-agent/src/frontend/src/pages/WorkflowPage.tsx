import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getWorkflowState,
  resumeWorkflow,
  pauseWorkflow,
  continueWorkflow,
  subscribeEvents,
  BackendUnreachableError,
  type WorkflowState,
  type ArtifactInfo,
  type TokenUsage,
} from "../api/client";
import CheckpointPlanView from "../components/CheckpointPlanView";
import ChapterReviewView from "../components/ChapterReviewView";
import CheckpointAudioView from "../components/CheckpointAudioView";
import ExecutionStream, {
  type ExecutionStep,
} from "../components/ExecutionStream";
import WorkflowSidebar from "../components/WorkflowSidebar";
import LoadingState from "../components/LoadingState";
import WorkflowPlan from "../components/WorkflowPlan";
import PresentationPreviewFab from "../components/PresentationPreviewFab";
import CheckpointReviewShell, {
  chapterReviewCollapsedLabel,
  isChapterReviewInterrupt,
} from "../components/CheckpointReviewShell";
import { canPreviewPresentation, resolvePresentationPreviewUrl } from "../utils/presentationPreview";

import { displayNodeLabel, formatElapsed, PLAN_MILESTONES, PLAN_ORDER } from "../workflow/nodeCatalog";

export default function WorkflowPage() {
  const { id: threadId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<WorkflowState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executionTrace, setExecutionTrace] = useState<ExecutionStep[]>([]);
  const [sseReady, setSseReady] = useState(false);
  const [clock, setClock] = useState(() => Date.now());
  const [pausing, setPausing] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [frozenElapsedMs, setFrozenElapsedMs] = useState<number | null>(null);
  const [previewCacheKey, setPreviewCacheKey] = useState(() => Date.now());
  const [chapterReviewOpen, setChapterReviewOpen] = useState(true);
  const revisionRef = useRef(0);
  const initialLoadDoneRef = useRef(false);

  useEffect(() => {
    setSseReady(false);
    setExecutionTrace([]);
    revisionRef.current = 0;
    initialLoadDoneRef.current = false;
  }, [threadId]);

  const applyState = useCallback((s: WorkflowState) => {
    setState(s);
    if (s.execution_trace?.length) {
      setExecutionTrace(s.execution_trace as ExecutionStep[]);
    }
    revisionRef.current = s.execution_revision ?? revisionRef.current;
  }, []);

  const handleThemeApplied = useCallback((themeId: string) => {
    setState((prev) =>
      prev ? { ...prev, selected_theme: themeId } : prev,
    );
    setPreviewCacheKey(Date.now());
  }, []);

  const fetchState = useCallback(async () => {
    if (!threadId) return;
    try {
      const s = await getWorkflowState(threadId);
      applyState(s);
      if (!initialLoadDoneRef.current) {
        revisionRef.current = s.execution_revision ?? 0;
        initialLoadDoneRef.current = true;
        setSseReady(true);
      }
      setLoading(false);
    } catch (e) {
      if (e instanceof BackendUnreachableError) return;
      setError(e instanceof Error ? e.message : "获取状态失败");
      setLoading(false);
    }
  }, [threadId, applyState]);

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  useEffect(() => {
    if (!threadId || !sseReady) return;
    const unsub = subscribeEvents(
      threadId,
      (event) => {
        if (event.type === "state_change" || event.completed_nodes) {
          setState((prev) =>
            prev
              ? {
                  ...prev,
                  current_phase: String(
                    event.current_phase ?? prev.current_phase,
                  ),
                  current_node: String(event.current_node ?? prev.current_node),
                  completed_nodes: (event.completed_nodes as string[]) ??
                    prev.completed_nodes,
                  pending_interrupt:
                    event.pending_interrupt !== undefined
                      ? (event.pending_interrupt as Record<string, unknown> | null)
                      : prev.pending_interrupt,
                  final_summary:
                    event.final_summary !== undefined
                      ? (event.final_summary as string | null)
                      : prev.final_summary,
                  token_usage:
                    event.token_usage !== undefined
                      ? (event.token_usage as TokenUsage)
                      : prev.token_usage,
                  presentation_url:
                    event.presentation_url !== undefined
                      ? (event.presentation_url as string | null)
                      : prev.presentation_url,
                  user_confirmations:
                    event.user_confirmations !== undefined
                      ? (event.user_confirmations as Record<string, unknown>)
                      : prev.user_confirmations,
                }
              : prev,
          );
        }
      },
      (data) => {
        if (data.trace) {
          setExecutionTrace(data.trace as ExecutionStep[]);
        }
        if (data.revision !== undefined) {
          revisionRef.current = data.revision as number;
        }
      },
      () => fetchState(),
      (err) => {
        if (err instanceof BackendUnreachableError) return;
        setError(err.message);
      },
      { from: revisionRef.current },
    );
    return unsub;
  }, [threadId, sseReady, fetchState]);

  const handleContinue = async () => {
    if (!threadId) return;
    setError(null);
    setContinuing(true);
    try {
      const res = await continueWorkflow(threadId);
      applyState(res.state);
      setFrozenElapsedMs(null);
    } catch (e) {
      if (e instanceof BackendUnreachableError) return;
      setError(e instanceof Error ? e.message : "继续失败");
    } finally {
      setContinuing(false);
    }
  };

  const handlePause = async () => {
    if (!threadId) return;
    setError(null);
    setPausing(true);
    try {
      const startedAt = executionTrace.length
        ? Math.min(...executionTrace.map((s) => s.started_at))
        : null;
      if (startedAt) {
        setFrozenElapsedMs(Date.now() - startedAt * 1000);
      }
      const res = await pauseWorkflow(threadId);
      applyState(res.state);
    } catch (e) {
      if (e instanceof BackendUnreachableError) return;
      setError(e instanceof Error ? e.message : "暂停失败");
      setFrozenElapsedMs(null);
    } finally {
      setPausing(false);
    }
  };

  const handleResume = async (confirmations: Record<string, unknown>) => {
    if (!threadId) return;
    setError(null);
    try {
      const res = await resumeWorkflow(threadId, confirmations);
      applyState(res.state);
    } catch (e) {
      if (e instanceof BackendUnreachableError) return;
      setError(e instanceof Error ? e.message : "提交确认失败");
    }
  };

  const interrupt = state?.pending_interrupt;
  const interruptType = (interrupt?.type as string) || undefined;
  const chapterReviewPending = isChapterReviewInterrupt(interruptType);

  const reviewInterruptKey = useMemo(() => {
    if (!chapterReviewPending || !interrupt) return "";
    return [
      interrupt.type,
      interrupt.chapter_index ?? "",
      interrupt.chapter_id ?? "",
    ].join(":");
  }, [chapterReviewPending, interrupt]);

  useEffect(() => {
    if (reviewInterruptKey) {
      setChapterReviewOpen(true);
    }
  }, [reviewInterruptKey]);
  const completedNodes = state?.completed_nodes ?? [];
  const artifacts: ArtifactInfo[] = state?.artifacts ?? [];
  const totalNodes = state?.total_nodes ?? 21;
  const isPaused = Boolean(state?.paused);

  const displayCurrentNode = useMemo(() => {
    if (state?.current_node) return state.current_node;
    const running = [...executionTrace].reverse().find((s) => s.status === "running");
    if (running) return running.node_id;
    if (executionTrace.length) {
      return executionTrace[executionTrace.length - 1].node_id;
    }
    return null;
  }, [state?.current_node, executionTrace]);

  const workflowStartedAt = useMemo(() => {
    if (!executionTrace.length) return null;
    return Math.min(...executionTrace.map((step) => step.started_at));
  }, [executionTrace]);

  const elapsedMs = useMemo(() => {
    if (!workflowStartedAt) return 0;
    if (isPaused && state?.paused_at) {
      return Math.max(0, (state.paused_at - workflowStartedAt) * 1000);
    }
    if (isPaused && frozenElapsedMs !== null) {
      return frozenElapsedMs;
    }
    return clock - workflowStartedAt * 1000;
  }, [workflowStartedAt, isPaused, state?.paused_at, frozenElapsedMs, clock]);

  useEffect(() => {
    if (!isPaused) {
      setFrozenElapsedMs(null);
    }
  }, [isPaused]);

  useEffect(() => {
    if (!workflowStartedAt || state?.final_summary || isPaused) return;
    const id = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [workflowStartedAt, state?.final_summary, isPaused]);

  if (loading) return <LoadingState message="加载工作流…" />;
  if (error) return <div className="error-box">{error}</div>;
  if (!state) return <div className="error-box">工作流未找到</div>;

  if (state.final_summary) {
    return (
      <div className="wf-done-page">
        <div className="wf-done-card">
          <h2>工作流完成</h2>
          <pre className="wf-done-summary">{state.final_summary}</pre>
          <div className="wf-done-actions">
            <button
              className="btn btn-primary"
              onClick={() => navigate(`/project/${threadId}`)}
            >
              查看产出
            </button>
            <button className="btn btn-ghost" onClick={() => navigate("/new")}>
              新建项目
            </button>
          </div>
        </div>
        {threadId && state && (
          <PresentationPreviewFab
            state={state}
            threadId={threadId}
            previewCacheKey={previewCacheKey}
            onThemeApplied={handleThemeApplied}
          />
        )}
      </div>
    );
  }

  const previewHref =
    threadId && state ? resolvePresentationPreviewUrl(state, threadId) : null;
  const showErrorPreview = Boolean(
    previewHref && (state.errors as unknown[])?.length > 0,
  );

  const isRunning = !interruptType && !isPaused;
  const awaitingChapterReview = chapterReviewPending && !chapterReviewOpen;
  const topbarNodeLabel = awaitingChapterReview
    ? "等待章节验收"
    : displayNodeLabel(displayCurrentNode);
  const showTimer = workflowStartedAt !== null;
  const showTransport = isRunning || isPaused;

  return (
    <div className="wf-shell">
      <header className="wf-topbar">
        <div className="wf-topbar-left">
          <span className="wf-topbar-title">Video Workflow</span>
        </div>
        <div className="wf-topbar-right">
          <span className="wf-topbar-count">
            {completedNodes.length} nodes
          </span>
          <div className="wf-topbar-progress">
            <div
              className="wf-topbar-progress-fill"
              style={{
                width: `${Math.min((completedNodes.length / totalNodes) * 100, 100)}%`,
              }}
            />
          </div>
        </div>

        <div
          className={`wf-topbar-stage${showTransport ? " has-transport" : ""}`}
          aria-label="工作流控制"
        >
          <div className="wf-topbar-stage-left">
            {isRunning && <span className="wf-topbar-dot" />}
            {isPaused && <span className="wf-topbar-dot wf-topbar-paused" />}
            {awaitingChapterReview && (
              <span className="wf-topbar-dot wf-topbar-waiting" />
            )}
            <span className="wf-topbar-node">{topbarNodeLabel}</span>
          </div>

          {showTransport && (
            <div className="wf-topbar-stage-core">
              {isPaused ? (
                <button
                  type="button"
                  className="wf-topbar-transport-btn is-continue"
                  onClick={handleContinue}
                  disabled={continuing}
                  aria-label="继续工作流"
                  title="继续"
                >
                  <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden>
                    <path d="M7 5.5v9l7-4.5-7-4.5z" fill="currentColor" />
                  </svg>
                  <span>{continuing ? "继续中…" : "继续"}</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="wf-topbar-transport-btn is-pause"
                  onClick={handlePause}
                  disabled={pausing}
                  aria-label="暂停工作流"
                  title="暂停"
                >
                  <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden>
                    <rect x="5" y="4" width="3.5" height="12" rx="1" fill="currentColor" />
                    <rect x="11.5" y="4" width="3.5" height="12" rx="1" fill="currentColor" />
                  </svg>
                  <span>{pausing ? "暂停中…" : "暂停"}</span>
                </button>
              )}
            </div>
          )}

          {showTimer && (
            <div className="wf-topbar-stage-right">
              <span
                className={`wf-topbar-timer${isPaused ? " is-frozen" : ""}`}
                aria-label="运行时长"
              >
                {formatElapsed(elapsedMs)}
              </span>
            </div>
          )}
        </div>
      </header>

      <div className="wf-grid">
        <main className="wf-console wf-clay-scroll">
          <WorkflowPlan
            milestones={PLAN_MILESTONES}
            planOrder={[...PLAN_ORDER]}
            completedNodes={completedNodes}
            currentNode={displayCurrentNode}
          />

          <ExecutionStream
            trace={executionTrace}
            workflowActive={isRunning}
          />

          {state.errors && (state.errors as any[]).length > 0 && (
            <div className="wf-validation wf-validation-error">
              <div className="wf-section-title">Errors</div>
              {showErrorPreview && previewHref && (
                <div className="cr-preview" style={{ marginBottom: 12 }}>
                  <p className="cr-preview-hint">
                    审查未通过时仍可预览当前章节效果，对照自检清单修改后点「继续」重试。
                  </p>
                  <a
                    className="btn btn-primary"
                    href={previewHref}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    预览演示网页 →
                  </a>
                </div>
              )}
              <div className="wf-validation-list">
                {(state.errors as any[]).map((err: any, i: number) => (
                  <div key={i} className="wf-validation-item">
                    <span className="wf-validation-icon wf-err-icon">✗</span>
                    <span className="wf-validation-msg">
                      {[
                        err.phase && `[${err.phase}]`,
                        err.node && err.node !== "wv_build_chapter_1" && err.node !== "wv_build_chapter_n"
                          ? err.node
                          : null,
                        err.error || err.message,
                      ]
                        .filter(Boolean)
                        .join(" ") || JSON.stringify(err)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        <WorkflowSidebar
            completedNodes={completedNodes}
            currentNode={displayCurrentNode}
            artifacts={artifacts}
          tokenUsage={state.token_usage}
        />
      </div>

      {/* 底部状态栏与顶栏重复，暂时隐藏
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
            {state.current_phase} · {completedNodes.length} / {totalNodes} nodes
          </span>
        </div>
      </footer>
      */}

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
        interruptType === "checkpoint_chapter_n" ||
        interruptType === "checkpoint_remaining_batch") &&
        interrupt && (
          <CheckpointReviewShell
            open={chapterReviewOpen}
            collapsedLabel={chapterReviewCollapsedLabel(interrupt)}
            onClose={() => setChapterReviewOpen(false)}
            onOpen={() => setChapterReviewOpen(true)}
          >
            <ChapterReviewView
              interrupt={interrupt}
              threadId={threadId!}
              workflowState={state}
              onResume={handleResume}
            />
          </CheckpointReviewShell>
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
          <div className="modal-card modal-card-simple wf-clay-scroll">
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

      {threadId && state && (
        <PresentationPreviewFab
          state={state}
          threadId={threadId}
          interruptType={interruptType}
          previewCacheKey={previewCacheKey}
          onThemeApplied={handleThemeApplied}
        />
      )}
    </div>
  );
}
