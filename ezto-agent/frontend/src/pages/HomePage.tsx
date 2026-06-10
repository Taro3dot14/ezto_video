import { useNavigate } from "react-router-dom";

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="page home-page">
      <div className="home-content">
        <h1 className="home-title">
          <span className="home-title-en">ezto-video</span>
          <span className="home-title-cn">网页视频演示工作流</span>
        </h1>
        <p className="home-desc">
          把文章或口播稿一步步做成可录屏的"伪装成视频的网页"。
          基于 LangGraph 状态机，完整复现 web-video-presentation 流程。
        </p>
        <div className="home-actions">
          <button className="btn btn-primary" onClick={() => navigate("/new")}>
            创建新项目
          </button>
        </div>
        <div className="home-phases">
          <div className="phase-list">
            <div className="phase-item">
              <span className="phase-num">1</span>
              <span>内容编写 → script.md + outline.md</span>
            </div>
            <div className="phase-item">
              <span className="phase-num">2</span>
              <span>Checkpoint Plan → 一次对齐 5 件事</span>
            </div>
            <div className="phase-item">
              <span className="phase-num">3</span>
              <span>网页开发 → 第 1 章强制验收 → 第 2~N 章</span>
            </div>
            <div className="phase-item">
              <span className="phase-num">4</span>
              <span>Checkpoint Audio → 可选音频合成</span>
            </div>
            <div className="phase-item">
              <span className="phase-num">5</span>
              <span>录屏 + 后期 → 成片输出</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
