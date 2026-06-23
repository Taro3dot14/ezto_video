import { useState, useEffect } from "react";
import { listThemes, readArtifact, type ThemeInfo } from "../api/client";

interface Props {
  interrupt: Record<string, unknown>;
  threadId: string;
  onResume: (confirmations: Record<string, unknown>) => void;
}

export default function CheckpointPlanView({ interrupt, threadId, onResume }: Props) {
  const [themes, setThemes] = useState<ThemeInfo[]>([]);
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);
  const [devMode, setDevMode] = useState<string>("A");
  const [materialPlan, setMaterialPlan] = useState<string>("b");
  const [scriptContent, setScriptContent] = useState<string | null>(null);
  const [outlineContent, setOutlineContent] = useState<string | null>(null);
  const [loadingThemes, setLoadingThemes] = useState(true);

  useEffect(() => {
    listThemes()
      .then(setThemes)
      .catch(() => {})
      .finally(() => setLoadingThemes(false));
  }, []);

  const files = interrupt.files as Record<string, string> | undefined;

  // Load script & outline content
  useEffect(() => {
    if (!threadId || !files) return;
    if (files.script) {
      readArtifact(threadId, files.script)
        .then((res) => setScriptContent(res.content))
        .catch(() => setScriptContent("（加载失败）"));
    }
    if (files.outline) {
      readArtifact(threadId, files.outline)
        .then((res) => setOutlineContent(res.content))
        .catch(() => setOutlineContent("（加载失败）"));
    }
  }, [threadId, files]);

  const recommendations = interrupt.theme_recommendations as
    | Array<{ id: string; nameZh: string; descriptionZh: string }>
    | undefined;

  const materialList = interrupt.material_list as string[] | undefined;

  const handleConfirm = () => {
    onResume({
      script_feedback: null,
      outline_feedback: null,
      selected_theme: selectedTheme || themes[0]?.id || "midnight-press",
      material_plan: materialPlan,
      development_mode: devMode,
    });
  };

  return (
    <div className="cp-view">
      <div className="cp-view-head">
        <h3>核对清单</h3>
        <p className="cp-desc">
          内容计划已写完。下面 5 件事一次确认，确认后进入网页开发阶段。
        </p>
      </div>

      <div className="cp-view-scroll wf-clay-scroll">
      {/* 1. Script */}
      <section className="cp-section">
        <h4>1. 口播稿 (script.md)</h4>
        <p className="cp-hint">文件：{files?.script ?? ""}</p>
        <textarea className="cp-file-content" readOnly rows={10}
          value={scriptContent ?? "加载中…"} />
        <p className="cp-hint">可以直接编辑文件，或口头告知修改方向。</p>
      </section>

      {/* 2. Outline */}
      <section className="cp-section">
        <h4>2. 开发计划 (outline.md)</h4>
        <p className="cp-hint">文件：{files?.outline ?? ""}</p>
        <textarea className="cp-file-content" readOnly rows={8}
          value={outlineContent ?? "加载中…"} />
        <p className="cp-hint">重点看：章节切分 / step 数 / 信息池 / 素材清单。</p>
      </section>

      {/* 3. Theme */}
      <section className="cp-section">
        <h4>3. 选择主题</h4>
        {loadingThemes ? (
          <p>加载主题中…</p>
        ) : (
          <div className="theme-grid">
            {(recommendations
              ? themes.filter((t) =>
                  recommendations.some((r) => r.id === t.id),
                )
              : themes
            ).map((theme) => (
              <button
                key={theme.id}
                className={`theme-card ${selectedTheme === theme.id ? "selected" : ""}`}
                onClick={() => setSelectedTheme(theme.id)}
              >
                <div className="theme-preview">
                  {theme.preview && (
                    <div className="theme-swatches">
                      <span
                        className="swatch"
                        style={{ background: theme.preview.shell }}
                      />
                      <span
                        className="swatch"
                        style={{ background: theme.preview.surface }}
                      />
                      <span
                        className="swatch"
                        style={{ background: theme.preview.accent }}
                      />
                    </div>
                  )}
                </div>
                <div className="theme-name">{theme.nameZh}</div>
                <div className="theme-desc">{theme.descriptionZh}</div>
                <div className="theme-tags">
                  {theme.bestFor.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* 4. Materials */}
      <section className="cp-section">
        <h4>4. 素材准备</h4>
        {materialList && materialList.length > 0 && (
          <ul className="material-list">
            {materialList.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        )}
        <div className="radio-group">
          <label className="radio-label">
            <input
              type="radio"
              checked={materialPlan === "b"}
              onChange={() => setMaterialPlan("b")}
            />
            <span>我自己提供素材</span>
          </label>
          <label className="radio-label">
            <input
              type="radio"
              checked={materialPlan === "a"}
              onChange={() => setMaterialPlan("a")}
            />
            <span>从现有素材路径帮你挑</span>
          </label>
          <label className="radio-label">
            <input
              type="radio"
              checked={materialPlan === "c"}
              onChange={() => setMaterialPlan("c")}
            />
            <span>全部用 placeholder</span>
          </label>
        </div>
      </section>

      {/* 5. Dev Mode */}
      <section className="cp-section">
        <h4>5. 开发模式</h4>
        <div className="radio-group">
          <label className="radio-label">
            <input
              type="radio"
              checked={devMode === "A"}
              onChange={() => setDevMode("A")}
            />
            <span>A) 逐章确认（推荐）</span>
          </label>
          <label className="radio-label">
            <input
              type="radio"
              checked={devMode === "B"}
              onChange={() => setDevMode("B")}
            />
            <span>B) 顺序开发，批量验收</span>
          </label>
          <label className="radio-label">
            <input
              type="radio"
              checked={devMode === "C"}
              onChange={() => setDevMode("C")}
            />
            <span>C) 并行开发（subagent）</span>
          </label>
        </div>
      </section>
      </div>

      <div className="cp-view-foot">
        <button className="btn btn-primary btn-lg" onClick={handleConfirm}>
          确认并继续
        </button>
      </div>
    </div>
  );
}
