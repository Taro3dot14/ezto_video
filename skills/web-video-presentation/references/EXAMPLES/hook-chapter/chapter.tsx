// ⚠️ Anchor 参考 — 实现时用 SceneChrome + lx-* shell，动画仅 ch-hk-* in index.css
import { MaskReveal } from "../../../templates/src/components/MaskReveal";
import { SceneChrome } from "../../../templates/src/components/SceneChrome";
import type { ChapterStepProps } from "../../../templates/src/registry/types";
import "./chapter.css";

const BRAND = "Hook Chapter";
const ISSUE = (rule: string) => `EXAMPLE · ${rule} · HOOK ANCHOR`;

/**
 * 钩子型开场 — lx-* 写法（结构骨架）
 * ghost grid → solo 逐张 → cover takeover → quote 收束
 */
export default function HookChapter({ step }: ChapterStepProps) {
  const reveals = [
    { src: "/hook/<asset-1>.png", label: "01 / 03", caption: "<反例 1，来自 article>" },
    { src: "/hook/<asset-2>.png", label: "02 / 03", caption: "<反例 2>" },
    { src: "/hook/<asset-3>.png", label: "03 / 03", caption: "<反例 3>" },
  ];

  if (step === 0) {
    return (
      <SceneChrome brand={BRAND} issue={ISSUE("ghost grid")}>
        <div className="lx-stack">
          <div className="lx-kicker">Hook · Ghost</div>
          <div className="lx-grid-3 ch-hk-ghost-grid">
            {["01", "02", "03"].map((num, idx) => (
              <MaskReveal show key={num} delay={idx * 200} duration={900}>
                <div className="ch-hk-ghost">
                  <span className="lx-caption">{num}</span>
                  <span className="lx-caption">image</span>
                </div>
              </MaskReveal>
            ))}
          </div>
        </div>
      </SceneChrome>
    );
  }

  if (step >= 1 && step <= 3) {
    const r = reveals[step - 1];
    return (
      <SceneChrome brand={BRAND} issue={ISSUE(`solo ${step}/3`)}>
        <div className="lx-solo">
          <div className="lx-solo-panel">
            <MaskReveal show duration={1100}>
              <div className="ch-hk-img-wrap">
                <img className="ch-hk-img" src={r.src} alt={r.caption} />
                <span className="ch-hk-stamp">FAKE?</span>
              </div>
            </MaskReveal>
            <MaskReveal show delay={400} duration={900}>
              <div className="lx-kicker">{r.label}</div>
              <p className="lx-body">{r.caption}</p>
            </MaskReveal>
          </div>
        </div>
      </SceneChrome>
    );
  }

  if (step === 4) {
    return (
      <SceneChrome brand={BRAND} issue={ISSUE("cover takeover")}>
        <div className="lx-cover-body ch-hk-takeover">
          <div className="ch-hk-mini-row">
            {reveals.map((r, idx) => (
              <img
                key={r.src}
                className="ch-hk-mini"
                src={r.src}
                alt={r.caption}
                style={{ animationDelay: `${idx * 80}ms` }}
              />
            ))}
          </div>
          <span className="ch-hk-accent-bar" />
          <h1 className="lx-hero">
            <MaskReveal show duration={1100}>
              &lt;主题大字 takeover&gt;
            </MaskReveal>
          </h1>
        </div>
      </SceneChrome>
    );
  }

  return (
    <SceneChrome brand={BRAND} issue={ISSUE("quote close")}>
      <div className="lx-quote-body">
        <div className="lx-kicker">Hook · Close</div>
        <div className="lx-quote-text ch-hk-quote-wrap">
          <h2 className="serif-cn">&lt;下一句钩子&gt;</h2>
          <span className="ch-hk-brush" aria-hidden />
        </div>
      </div>
    </SceneChrome>
  );
}
