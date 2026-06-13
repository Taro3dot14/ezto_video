import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { startWorkflow } from "../api/client";

export default function NewProjectPage() {
  const navigate = useNavigate();
  const [inputType, setInputType] = useState<"article" | "script">("article");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await startWorkflow(content, "zh-CN", inputType);
      navigate(`/workflow/${res.thread_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page new-project-page">
      <div className="np-header">
        <button className="btn btn-ghost" onClick={() => navigate("/")}>
          ← 返回
        </button>
        <h2>创建新项目</h2>
      </div>

      <div className="np-input-type">
        <label className="radio-label">
          <input
            type="radio"
            checked={inputType === "article"}
            onChange={() => setInputType("article")}
          />
          <span>原始文章（公众号/博客/论文）</span>
        </label>
        <label className="radio-label">
          <input
            type="radio"
            checked={inputType === "script"}
            onChange={() => setInputType("script")}
          />
          <span>口播稿 / 视频脚本（已有稿子）</span>
        </label>
      </div>

      <textarea
        className="np-textarea"
        placeholder={
          inputType === "article"
            ? "粘贴你的文章内容…"
            : "粘贴你的口播稿…"
        }
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={16}
      />

      {error && <div className="error-box">{error}</div>}

      <button
        className="btn btn-primary"
        onClick={handleSubmit}
        disabled={!content.trim() || submitting}
      >
        {submitting ? "启动中…" : "开始制作"}
      </button>
    </div>
  );
}
