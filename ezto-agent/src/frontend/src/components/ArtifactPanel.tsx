import { useEffect, useState } from "react";
import { listArtifacts, readArtifact, type ArtifactInfo } from "../api/client";

interface Props {
  threadId: string;
}

export default function ArtifactPanel({ threadId }: Props) {
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listArtifacts(threadId)
      .then((res) => setArtifacts(res.artifacts))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [threadId]);

  const handlePreview = async (a: ArtifactInfo) => {
    if (!a.exists) return;
    try {
      const res = await readArtifact(threadId, a.logical_name);
      setPreviewPath(a.logical_name);
      setPreviewContent(res.content);
    } catch {
      // ignore
    }
  };

  return (
    <div className="artifact-panel">
      <h4 className="ap-title">产出文件</h4>
      {loading ? (
        <p className="ap-loading">加载中…</p>
      ) : artifacts.length === 0 ? (
        <p className="ap-empty">暂无产出文件</p>
      ) : (
        <ul className="ap-list">
          {artifacts.map((a) => (
            <li key={a.logical_name} className="ap-item">
              <button
                className="ap-link"
                onClick={() => handlePreview(a)}
                title={a.exists ? "点击预览" : "文件尚未生成"}
              >
                <span className={`ap-status ${a.exists ? "exists" : "missing"}`} />
                {a.logical_name}
              </button>
              {a.size != null && a.exists && (
                <span className="ap-size">
                  {(a.size / 1024).toFixed(1)} KB
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {previewContent && (
        <div className="ap-preview">
          <div className="ap-preview-header">
            <span>{previewPath}</span>
            <button className="btn-close" onClick={() => setPreviewContent(null)}>
              关闭
            </button>
          </div>
          <pre className="ap-preview-body">{previewContent.slice(0, 2000)}</pre>
          {previewContent.length > 2000 && (
            <p className="ap-truncated">内容过长，仅显示前 2000 字符</p>
          )}
        </div>
      )}
    </div>
  );
}
