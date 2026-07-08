// ⚠️ Anchor 参考 — SceneChrome + ListGrid/GridSlot；动画仅 ch-lr-* in index.css
import { GridSlot, ListGrid } from "../../../templates/src/components/GridSlot";
import { MaskReveal } from "../../../templates/src/components/MaskReveal";
import { SceneChrome } from "../../../templates/src/components/SceneChrome";
import type { ChapterStepProps } from "../../../templates/src/registry/types";
import "./chapter.css";

const BRAND = "List Reveal";
const ISSUE = (rule: string) => `EXAMPLE · ${rule} · LIST ANCHOR`;

const ITEMS = [
  { num: "01", title: "<第 1 项标题>", body: "<article 抽来的细节>" },
  { num: "02", title: "<第 2 项标题>", body: "<细节>" },
  { num: "03", title: "<第 3 项标题>", body: "<细节>" },
];

function slotState(step: number, index: number): "ghost" | "active" | "past" {
  const active = step - 1;
  if (index < active) return "past";
  if (index === active) return "active";
  return "ghost";
}

/**
 * 列举型 — lx-grid-3 + GridSlot（1 项 / step）
 */
export default function ListRevealChapter({ step }: ChapterStepProps) {
  if (step === 0) {
    return (
      <SceneChrome brand={BRAND} issue={ISSUE("intro")}>
        <div className="lx-stack lx-stack-center">
          <div className="lx-kicker">List · Intro</div>
          <h1 className="lx-title">
            <MaskReveal show duration={900}>
              <span className="serif-cn">强在</span>
              <span className="ex-em">哪</span>
            </MaskReveal>
          </h1>
          <p className="lx-body lx-caption">三件事 — 一个个看</p>
        </div>
      </SceneChrome>
    );
  }

  const activeIdx = step - 1;
  return (
    <SceneChrome brand={BRAND} issue={ISSUE(`slot ${ITEMS[activeIdx]?.num ?? step}`)}>
      <div className="lx-kicker">List · Grid 3</div>
      <h2 className="lx-subtitle">一项一个 step — ghost / active / past</h2>
      <ListGrid>
        {ITEMS.map((item, idx) => (
          <GridSlot
            key={item.num}
            state={slotState(step, idx)}
            num={item.num}
            title={item.title}
            body={idx === activeIdx ? item.body : undefined}
          />
        ))}
      </ListGrid>
    </SceneChrome>
  );
}
