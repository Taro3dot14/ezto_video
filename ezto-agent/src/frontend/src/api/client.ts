/** API client for the ezto-video backend. */

const BASE = "/api";

export interface ThemeInfo {
  id: string;
  name: string;
  nameZh: string;
  description: string;
  descriptionZh: string;
  mood: string[];
  bestFor: string[];
  preview: Record<string, string> | null;
}

export interface ArtifactInfo {
  logical_name: string;
  path: string;
  exists: boolean;
  size: number | null;
}

export interface WorkflowState {
  thread_id: string;
  current_phase: string;
  current_node: string;
  completed_nodes: string[];
  thinking_log?: Record<string, unknown>[];
  pending_interrupt: Record<string, unknown> | null;
  errors: Record<string, unknown>[];
  artifacts: ArtifactInfo[];
  selected_theme: string | null;
  selected_mode: string | null;
  final_summary: string | null;
  presentation_url: string | null;
  validation_results?: Record<string, unknown>[];
  repair_history?: Record<string, unknown>[];
  user_confirmations?: Record<string, unknown>;
}

export interface StartResponse {
  thread_id: string;
  state: WorkflowState;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function startWorkflow(
  userRequest: string,
  language = "zh-CN",
  inputType?: string,
): Promise<StartResponse> {
  return request("/workflow/start", {
    method: "POST",
    body: JSON.stringify({ user_request: userRequest, language, input_type: inputType }),
  });
}

export async function resumeWorkflow(
  threadId: string,
  confirmations: Record<string, unknown>,
): Promise<{ thread_id: string; state: WorkflowState }> {
  return request(`/workflow/${threadId}/resume`, {
    method: "POST",
    body: JSON.stringify({ confirmations }),
  });
}

export async function getWorkflowState(threadId: string): Promise<WorkflowState> {
  return request(`/workflow/${threadId}`);
}

export async function listArtifacts(threadId: string): Promise<{ artifacts: ArtifactInfo[] }> {
  return request(`/workflow/${threadId}/artifacts`);
}

export async function readArtifact(threadId: string, path: string): Promise<{ content: string }> {
  return request(`/workflow/${threadId}/artifact/${encodeURIComponent(path)}`);
}

export async function listThemes(): Promise<ThemeInfo[]> {
  return request("/themes");
}

export function subscribeEvents(
  threadId: string,
  onData: (event: Record<string, unknown>) => void,
  onThink?: (events: Record<string, unknown>[]) => void,
  onComplete?: () => void,
  onError?: (err: Error) => void,
): () => void {
  const es = new EventSource(`${BASE}/workflow/${threadId}/events`);

  // Handle named events (think, completed)
  es.addEventListener("think", (ev) => {
    try {
      const data = JSON.parse(ev.data);
      onThink?.(data);
    } catch { /* ignore */ }
  });

  es.addEventListener("completed", (ev) => {
    try {
      const data = JSON.parse(ev.data);
      onData({ type: "completed", ...data });
      es.close();
      onComplete?.();
    } catch { /* ignore */ }
  });

  // Default message event (state_change)
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "state_change" || data.completed_nodes) {
        onData(data);
        if (data.final_summary) {
          es.close();
          onComplete?.();
        }
      }
    } catch {
      // ignore parse errors
    }
  };

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      onError?.(new Error("SSE connection closed"));
    }
  };
  return () => es.close();
}
