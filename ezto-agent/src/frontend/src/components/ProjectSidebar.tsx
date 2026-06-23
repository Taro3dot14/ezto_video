import { useCallback, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  listProjects,
  renameProject,
  deleteProject,
  type ProjectSummary,
} from "../api/client";
import { useProjectList } from "../contexts/ProjectListContext";
import PanelCollapseToggle from "./PanelCollapseToggle";

const COLLAPSED_KEY = "ezto-project-sidebar-collapsed";

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

function projectHref(project: ProjectSummary): string {
  if (project.is_active || project.status === "in_progress") {
    return `/workflow/${project.id}`;
  }
  return `/project/${project.id}`;
}

interface Props {
  onProjectsChange?: () => void;
}

export default function ProjectSidebar({ onProjectsChange }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { revision, refreshProjects } = useProjectList();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      const rows = await listProjects();
      setProjects(rows);
      setFetchError(null);
    } catch (e) {
      setProjects([]);
      setFetchError(e instanceof Error ? e.message : "加载项目失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchProjects();
  }, [fetchProjects, location.pathname, revision]);

  useEffect(() => {
    const onFocus = () => fetchProjects();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [fetchProjects]);

  useEffect(() => {
    onProjectsChange?.();
  }, [projects, onProjectsChange]);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const startRename = (project: ProjectSummary, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setEditingId(project.id);
    setEditName(project.name);
    setRenameError(null);
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditName("");
    setRenameError(null);
  };

  const submitRename = async (projectId: string) => {
    const name = editName.trim();
    if (!name) {
      setRenameError("名称不能为空");
      return;
    }
    try {
      await renameProject(projectId, name);
      setProjects((prev) =>
        prev.map((p) => (p.id === projectId ? { ...p, name } : p)),
      );
      cancelRename();
    } catch (e) {
      setRenameError(e instanceof Error ? e.message : "重命名失败");
    }
  };

  const requestDelete = (project: ProjectSummary, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDeleteTarget(project);
    setDeleteError(null);
  };

  const cancelDelete = () => {
    if (deleting) return;
    setDeleteTarget(null);
    setDeleteError(null);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteProject(deleteTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      refreshProjects();

      const onDeletedProject =
        location.pathname.includes(`/workflow/${deleteTarget.id}`) ||
        location.pathname.includes(`/project/${deleteTarget.id}`);
      if (onDeletedProject) {
        navigate("/");
      }

      setDeleteTarget(null);
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <aside
      className={`project-sidebar${collapsed ? " is-collapsed" : ""}`}
      aria-label="项目管理"
    >
      <div className="project-sidebar-head">
        {!collapsed && (
          <NavLink to="/" className="project-sidebar-brand" title="ezto-video">
            <span className="project-sidebar-logo">ez</span>
            <span className="project-sidebar-title">ezto-video</span>
          </NavLink>
        )}
        <PanelCollapseToggle
          expanded={!collapsed}
          onToggle={toggleCollapsed}
          expandLabel="展开项目栏"
          collapseLabel="收起项目栏"
          controlsId="project-sidebar-list"
          className="project-sidebar-toggle"
          direction="horizontal"
          iconOnly
        />
      </div>

      <button
        type="button"
        className="project-sidebar-new"
        onClick={() => navigate("/new")}
        title="创建新项目"
      >
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden>
          <path
            d="M10 4v12M4 10h12"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
        {!collapsed && <span>新建项目</span>}
      </button>

      <div
        id="project-sidebar-list"
        className="project-sidebar-list"
        hidden={collapsed}
      >
        {loading ? (
          <div className="project-sidebar-empty">加载中…</div>
        ) : fetchError ? (
          <div className="project-sidebar-empty project-sidebar-error">
            {fetchError}
          </div>
        ) : projects.length === 0 ? (
          <div className="project-sidebar-empty">暂无历史项目</div>
        ) : (
          <ul className="project-sidebar-items" role="list">
            {projects.map((project) => {
              const isEditing = editingId === project.id;
              return (
                <li key={project.id} className="project-sidebar-item-wrap">
                  {isEditing ? (
                    <div className="project-sidebar-rename">
                      <input
                        className="project-sidebar-rename-input"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") submitRename(project.id);
                          if (e.key === "Escape") cancelRename();
                        }}
                        autoFocus
                        aria-label="项目名称"
                      />
                      <div className="project-sidebar-rename-actions">
                        <button
                          type="button"
                          className="project-sidebar-rename-btn"
                          onClick={() => submitRename(project.id)}
                        >
                          保存
                        </button>
                        <button
                          type="button"
                          className="project-sidebar-rename-btn is-cancel"
                          onClick={cancelRename}
                        >
                          取消
                        </button>
                      </div>
                      {renameError && (
                        <div className="project-sidebar-rename-error">
                          {renameError}
                        </div>
                      )}
                    </div>
                  ) : (
                    <NavLink
                      to={projectHref(project)}
                      className={({ isActive }) =>
                        [
                          "project-sidebar-item",
                          isActive ? "is-active" : "",
                          project.is_active ? "is-running" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")
                      }
                      title={project.name}
                    >
                      <span className="project-sidebar-item-icon" aria-hidden>
                        {project.is_active ? (
                          <span className="project-sidebar-dot" />
                        ) : (
                          <svg viewBox="0 0 20 20" width="16" height="16">
                            <path
                              d="M4 6a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V6z"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.5"
                            />
                          </svg>
                        )}
                      </span>
                      <span className="project-sidebar-item-body">
                        <span className="project-sidebar-item-name">
                          {project.name}
                        </span>
                        <span className="project-sidebar-item-meta">
                          {statusLabel(project.status)}
                          {project.artifact_count > 0 &&
                            ` · ${project.artifact_count} 个产出`}
                        </span>
                      </span>
                      <div className="project-sidebar-actions">
                        <button
                          type="button"
                          className="project-sidebar-edit"
                          onClick={(e) => startRename(project, e)}
                          aria-label={`重命名 ${project.name}`}
                          title="重命名"
                        >
                          <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden>
                            <path
                              d="M13.5 3.5l3 3L7 16H4v-3L13.5 3.5z"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.5"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                        <button
                          type="button"
                          className="project-sidebar-delete"
                          onClick={(e) => requestDelete(project, e)}
                          aria-label={`删除 ${project.name}`}
                          title="删除"
                        >
                          <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden>
                            <path
                              d="M6 7h8M8 7V5.5h4V7m-1 0v8.5H9V7M7.5 7l.5 8.5m5-8.5l-.5 8.5"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                      </div>
                    </NavLink>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {collapsed && projects.length > 0 && (
        <div className="project-sidebar-collapsed-hint" title={`${projects.length} 个项目`}>
          <span className="project-sidebar-count">{projects.length}</span>
        </div>
      )}

      {deleteTarget && (
        <div
          className="modal-overlay project-delete-overlay"
          role="presentation"
          onClick={cancelDelete}
        >
          <div
            className="modal-card project-delete-dialog"
            role="alertdialog"
            aria-labelledby="project-delete-title"
            aria-describedby="project-delete-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="project-delete-title" className="project-delete-title">
              确认删除项目？
            </h3>
            <p id="project-delete-desc" className="project-delete-desc">
              将永久删除「{deleteTarget.name}」及其所有产出文件，此操作不可恢复。
            </p>
            {deleteError && (
              <div className="project-delete-error">{deleteError}</div>
            )}
            <div className="project-delete-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={cancelDelete}
                disabled={deleting}
              >
                取消
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={confirmDelete}
                disabled={deleting}
              >
                {deleting ? "删除中…" : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
