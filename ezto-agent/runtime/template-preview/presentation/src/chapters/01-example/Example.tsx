import { MaskReveal } from "../../components/MaskReveal";
import { GridSlot, ListGrid } from "../../components/GridSlot";
import { SceneChrome } from "../../components/SceneChrome";
import type { ChapterStepProps } from "../../registry/types";
import "./Example.css";

const BRAND = "Layout Shell Lab";

/**
 * Layout Shell Lab — reference chapter for all agents.
 *
 * Steps: cover → split → grid-3 (list-reveal) → quote.
 */
export default function ExampleChapter({ step }: ChapterStepProps) {
  if (step === 0) {
    return (
      <SceneChrome
        brand={BRAND}
        issue="EXAMPLE 01 · RULE 01 · READ LAYOUT-SYSTEM.MD"
      >
        <div className="lx-cover-body">
          <div className="lx-kicker">Shell · Cover</div>
          <h1 className="lx-hero">
            <MaskReveal show duration={900}>
              <span className="serif-cn">固定舞台</span>
            </MaskReveal>
            <br />
            <MaskReveal show delay={300} duration={900}>
              <span className="display-en-soft ex-em">排版锁在 shell</span>
            </MaskReveal>
          </h1>
          <p className="lx-body">
            Agent 只填内容与 ch-* 动画，不发明 font-size 或 gap。
          </p>
          <div className="lx-cover-foot lx-caption">
            <span className="dot-accent" /> Tap to advance
          </div>
        </div>
      </SceneChrome>
    );
  }

  if (step === 1) {
    return (
      <SceneChrome
        brand={BRAND}
        issue="EXAMPLE 01 · RULE 02 · READ LAYOUT-SYSTEM.MD"
      >
        <section className="lx-split-section" aria-label="Split shell demo">
          <div className="lx-split-rail">
            <span className="lx-split-index" aria-hidden>
              02
            </span>
          </div>
          <div className="lx-split-module">
            <div className="lx-split-rule" aria-hidden />
            <article className="lx-split-panel">
              <div className="lx-split-panel-main">
                <div className="lx-kicker">Shell · Split</div>
                <h2 className="lx-title">
                  <MaskReveal show duration={900}>
                    <span className="serif-cn">大数字 + 正文</span>
                  </MaskReveal>
                </h2>
                <p className="lx-body">
                  左侧 accent 数字轨，右侧 surface 面板 — 垂直居中，不再头重脚轻。
                </p>
              </div>
              <footer className="lx-split-foot">
                <span className="lx-split-foot-label">Layout rule</span>
                <span className="lx-split-foot-value">
                  Rail · rule · panel — one unified section
                </span>
              </footer>
            </article>
          </div>
        </section>
      </SceneChrome>
    );
  }

  if (step === 2) {
    return (
      <SceneChrome
        brand={BRAND}
        issue="EXAMPLE 01 · RULE 03 · READ LAYOUT-SYSTEM.MD"
      >
        <div className="lx-kicker">Shell · Grid 3 — one item per step</div>
        <h2 className="lx-subtitle">列举时：ghost → active → past</h2>
        <ListGrid>
          <GridSlot
            state="past"
            num="01"
            title="已讲过的项"
            body="past 态保留上下文，灰化。"
          />
          <GridSlot
            state="active"
            num="02"
            title="当前 step 独占"
            body="active 态高亮边框 + 数字砸下动画。"
          />
          <GridSlot
            state="ghost"
            num="03"
            title="尚未揭示"
            body="ghost 态虚线占位。"
          />
        </ListGrid>
      </SceneChrome>
    );
  }

  return (
    <SceneChrome
      brand={BRAND}
      issue="EXAMPLE 01 · RULE 04 · READ LAYOUT-SYSTEM.MD"
    >
      <div className="lx-quote-body">
        <div className="lx-kicker">Shell · Quote</div>
        <div className="pull-quote lx-quote-text">
          <MaskReveal show duration={1100}>
            <span className="serif-cn">换章节时</span>
          </MaskReveal>
          <MaskReveal show delay={400} duration={1100}>
            <span className="display-en-soft ex-em">&nbsp;只换内容与动画</span>
          </MaskReveal>
        </div>
        <div className="lx-caption">layouts/LAYOUT-SYSTEM.md · CHAPTER-CRAFT.md</div>
      </div>
    </SceneChrome>
  );
}
