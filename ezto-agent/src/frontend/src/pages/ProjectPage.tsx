import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getProject,
  renameProject,
  readProjectArtifact,
  type ProjectDetail,
} from "../api/client";
import LoadingState from "../components/LoadingState";
import ThemeSwitcherPopover from "../components/ThemeSwitcherPopover";

function fmtSize(bytes: number | null | undefined): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusLabel(status: string): string {
  switch (status) {
    case "completed":
      return "已完成";
    case "in_progress":
      return "进行中";
    case "empty":
      return "空项目";
    default:
      return status;
  }
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);

  const fetchProject = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getProject(id);
      setProject(data);
      setNameInput(data.name);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    setLoading(true);
    fetchProject();
  }, [fetchProject]);

  const handlePreview = async (logicalName: string) => {
    if (!id) return;
    try {
      const res = await readProjectArtifact(id, logicalName);
      setPreviewPath(logicalName);
      setPreviewContent(res.content);
    } catch {
      setError("无法读取文件");
    }
  };

  const handleRename = async () => {
    if (!id || !nameInput.trim()) return;
    setRenameError(null);
    try {
      const updated = await renameProject(id, nameInput.trim());
      setProject((prev) => (prev ? { ...prev, name: updated.name } : prev));
      setEditingName(false);
    } catch (e) {
      setRenameError(e instanceof Error ? e.message : "重命名失败");
    }
  };

  if (loading) return <LoadingState message="加载项目…" />;
  if (error && !project) return <div className="error-box">{error}</div>;
  if (!project) return <div className="error-box">项目未找到</div>;

  const generated = project.artifacts.filter((a) => a.exists);
  const pending = project.artifacts.filter((a) => !a.exists);
  const hasPresentation = generated.some((a) => a.logical_name === "presentation");

  return (
    <div className="page project-page">
      <header className="project-page-header">
        <div className="project-page-title-row">
          {editingName ? (
            <div className="project-page-rename">
              <input
                className="project-page-rename-input"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRename();
                  if (e.key === "Escape") {
                    setEditingName(false);
                    setNameInput(project.name);
                  }
                }}
                autoFocus
                aria-label="项目名称"
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleRename}
              >
                保存
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setEditingName(false);
                  setNameInput(project.name);
                }}
              >
                取消
              </button>
            </div>
          ) : (
            <>
              <h1 className="project-page-title">{project.name}</h1>
              <button
                type="button"
                className="project-page-edit-btn"
                onClick={() => setEditingName(true)}
                aria-label="重命名项目"
                title="重命名"
              >
                <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden>
                  <path
                    d="M13.5 3.5l3 3L7 16H4v-3L13.5 3.5z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </>
          )}
        </div>
        {renameError && <div className="error-box">{renameError}</div>}

        <div className="project-page-meta">
          <span className={`project-status project-status-${project.status}`}>
            {statusLabel(project.status)}
          </span>
          {project.is_active && (
            <span className="project-status project-status-active">运行中</span>
          )}
          <span className="project-page-date">
            更新于 {new Date(project.updated_at).toLocaleString("zh-CN")}
          </span>
        </div>

        {project.user_request && (
          <p className="project-page-desc">{project.user_request}</p>
        )}

        <div className="project-page-actions">
          {(project.is_active || project.status === "in_progress") && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate(`/workflow/${project.id}`)}
            >
              打开工作流
            </button>
          )}
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => navigate("/new")}
          >
            新建项目
          </button>
          {hasPresentation && id && (
            <ThemeSwitcherPopover
              projectId={id}
              selectedTheme={selectedTheme}
              visible
              inline
              onThemeApplied={setSelectedTheme}
            />
          )}
        </div>
      </header>

      <section className="project-artifacts">
        <h2 className="project-section-title">产出文件</h2>

        {generated.length === 0 && pending.length === 0 ? (
          <p className="project-empty">暂无产出文件</p>
        ) : (
          <div className="project-artifact-grid">
            {generated.length > 0 && (
              <div className="project-artifact-group">
                <h3 className="project-artifact-group-title">已生成</h3>
                <ul className="project-artifact-list" role="list">
                  {generated.map((a) => (
                    <li key={a.logical_name}>
                      <button
                        type="button"
                        className="project-artifact-btn"
                        onClick={() => handlePreview(a.logical_name)}
                        title="点击预览"
                      >
                        <span className="project-artifact-check" aria-hidden />
                        <span className="project-artifact-name">
                          {a.logical_name}
                        </span>
                        <span className="project-artifact-size">
                          {fmtSize(a.size)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {pending.length > 0 && (
              <div className="project-artifact-group">
                <h3 className="project-artifact-group-title">待生成</h3>
                <ul className="project-artifact-list" role="list">
                  {pending.map((a) => (
                    <li key={a.logical_name}>
                      <div className="project-artifact-btn is-pending">
                        <span className="project-artifact-pending" aria-hidden />
                        <span className="project-artifact-name">
                          {a.logical_name}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {previewContent && (
          <div className="project-preview">
            <div className="project-preview-header">
              <span>{previewPath}</span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setPreviewContent(null);
                  setPreviewPath(null);
                }}
              >
                关闭
              </button>
            </div>
            <pre className="project-preview-body">
              {previewContent.slice(0, 4000)}
            </pre>
            {previewContent.length > 4000 && (
              <p className="project-preview-truncated">
                内容过长，仅显示前 4000 字符
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
