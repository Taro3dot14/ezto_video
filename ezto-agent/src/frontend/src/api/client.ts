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

  relative_path?: string;

}



export interface ProjectSummary {
  id: string;
  name: string;
  status: string;
  artifact_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  input_type: string | null;
}

export interface ProjectDetail extends ProjectSummary {
  user_request: string;
  language: string;
  artifacts: ArtifactInfo[];
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

  events: { type: string; content: string; ts: number }[];

}



export interface ModelTokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  calls: number;
}

export interface TokenUsage {
  revision?: number;
  by_model: Record<string, ModelTokenUsage>;
  total: ModelTokenUsage;
}

export interface WorkflowState {

  thread_id: string;

  current_phase: string;

  current_node: string;

  completed_nodes: string[];

  execution_trace?: ExecutionStep[];

  execution_revision?: number;

  total_nodes?: number;
  token_usage?: TokenUsage;
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

  paused?: boolean;

  paused_at?: number | null;

}



export interface StartResponse {

  thread_id: string;

  state: WorkflowState;

}



export class BackendUnreachableError extends Error {
  constructor() {
    super("后端服务不可用");
    this.name = "BackendUnreachableError";
  }
}

function redirectToHome(): void {
  const path = window.location.pathname;
  if (path === "/" || path === "") return;
  window.location.replace("/");
}

function isNetworkFetchError(err: unknown): boolean {
  return (
    err instanceof TypeError &&
    /failed to fetch|networkerror|load failed|network request failed/i.test(err.message)
  );
}

function isBackendUnreachableStatus(
  status: number,
  body: { detail?: string; message?: string },
): boolean {
  if (status === 502 || status === 503 || status === 504) return true;
  // Vite dev proxy returns bare 500 when backend is down (ECONNREFUSED).
  if (status === 500 && !body.detail && !body.message) return true;
  return false;
}

async function parseErrorBody(
  res: Response,
): Promise<{ detail?: string; message?: string }> {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json().catch(() => ({}));
  }
  return {};
}

function handleBackendUnreachable(): never {
  redirectToHome();
  throw new BackendUnreachableError();
}



async function request<T>(path: string, options?: RequestInit): Promise<T> {

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {

      headers: { "Content-Type": "application/json" },

      ...options,

    });
  } catch (err) {
    if (isNetworkFetchError(err)) handleBackendUnreachable();
    throw err;
  }

  if (!res.ok) {

    const body = await parseErrorBody(res);
    if (isBackendUnreachableStatus(res.status, body)) handleBackendUnreachable();

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



export async function pauseWorkflow(

  threadId: string,

): Promise<{ thread_id: string; state: WorkflowState }> {

  return request(`/workflow/${threadId}/pause`, {

    method: "POST",

    body: JSON.stringify({}),

  });

}



export async function continueWorkflow(

  threadId: string,

): Promise<{ thread_id: string; state: WorkflowState }> {

  return request(`/workflow/${threadId}/continue`, {

    method: "POST",

    body: JSON.stringify({}),

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



export async function listProjects(): Promise<ProjectSummary[]> {
  return request("/projects");
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  return request(`/projects/${projectId}`);
}

export async function renameProject(
  projectId: string,
  name: string,
): Promise<ProjectSummary> {
  return request(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function deleteProject(
  projectId: string,
): Promise<{ deleted: boolean; id: string; name: string }> {
  return request(`/projects/${projectId}`, { method: "DELETE" });
}

export async function listProjectArtifacts(
  projectId: string,
): Promise<{ artifacts: ArtifactInfo[] }> {
  return request(`/projects/${projectId}/artifacts`);
}

export async function readProjectArtifact(
  projectId: string,
  path: string,
): Promise<{ content: string; path: string }> {
  return request(
    `/projects/${projectId}/artifact/${encodeURIComponent(path)}`,
  );
}



export interface TracePayload {

  trace: ExecutionStep[];

  revision: number;

}



export function subscribeEvents(

  threadId: string,

  onData: (event: Record<string, unknown>) => void,

  onTrace?: (data: TracePayload) => void,

  onComplete?: () => void,

  onError?: (err: Error) => void,

  options?: { from?: number },

): () => void {

  const params = new URLSearchParams();

  if (options?.from) params.set("from", String(options.from));

  const qs = params.toString();

  const url = `${BASE}/workflow/${threadId}/events${qs ? `?${qs}` : ""}`;

  const es = new EventSource(url);

  let sseOpened = false;

  es.onopen = () => {
    sseOpened = true;
  };



  es.addEventListener("trace", (ev) => {

    try {

      const data = JSON.parse(ev.data) as TracePayload;

      onTrace?.(data);

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

    if (!sseOpened) {
      es.close();
      handleBackendUnreachable();
      return;
    }

    if (es.readyState === EventSource.CLOSED) {
      es.close();
      handleBackendUnreachable();
    }

  };

  return () => es.close();

}

