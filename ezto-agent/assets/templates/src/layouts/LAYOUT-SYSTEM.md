# Layout Shell System

> **First principle:** This is a **recorded 1920×1080 video**, not a responsive website.
> Layout, typography scale, and whitespace are **fixed in `layouts.css`**.
> Chapters **pick a shell + fill slots** — never invent spacing or font-size from scratch.

## The stack

```
Stage (1920×1080, scale to viewport)
  └── SceneChrome (scene-pad + masthead + rule + lx-body-fill)
        └── Layout shell (lx-cover | lx-split | …)
              └── Content slots (lx-hero, lx-body, …)
                    └── Chapter animations (ch-* in index.css only)
```

## Shell picker (decision tree)

```
这一步要做什么？
├─ 开场 / 一个大标语           → lx-cover
├─ 左数字 + 右解释             → lx-split
├─ 单一主视觉（图/演示）       → lx-solo
├─ 口播「第一…第二…第三…」     → lx-grid-3 + GridSlot（1 项/step）
├─ 两个方案对比                → lx-grid-2
├─ 代码 / 终端 / 对话窗        → lx-terminal
├─ 章节引言 / 过渡             → lx-stack
└─ 收尾金句                    → lx-quote
```

## Typography roles (mandatory)

| Class | Token | Use for |
|-------|-------|---------|
| `.lx-hero` | `--t-display-1` | Opening headline (max **14ch**) |
| `.lx-title` | `--t-h1` | Section title (max **18ch**) |
| `.lx-subtitle` | `--t-h2` | Card / slot title |
| `.lx-body` | `--t-projection-body` | Readable copy (max **42ch**, lh 1.5) |
| `.lx-caption` | `--t-projection-caption` | Footnotes, mono labels |
| `.lx-kicker` | `--t-projection-caption` | Uppercase accent label |
| `.lx-hero-num` | `--t-display-1` | Large step numbers |

**Do not** set raw `font-size: 28px` on primary copy. Use roles above.

## Layout shells (pick one per step)

| Shell | Classes | When to use |
|-------|---------|-------------|
| **Cover** | `.lx-cover-body` | Hero opener |
| **Solo** | `.lx-solo` + `.lx-solo-panel` | Single demo (78% width) |
| **Split** | `.lx-split-section` + rail / rule / panel | Rule index + content card (unified section) |
| **Grid 3** | `<ListGrid>` + `<GridSlot>` | List reveal — **1 active slot per step** |
| **Grid 2** | `.lx-grid-2` | A vs B comparison |
| **Quote** | `.lx-quote-body` + `.lx-quote-text` | Closing pull-quote |
| **Stack** | `.lx-stack` / `.lx-stack-center` | Intro / transition |
| **Terminal** | `.lx-terminal` + `.lx-terminal-window` | Code / chat |

### GridSlot component (list reveal)

```tsx
import { GridSlot, ListGrid } from "../../components/GridSlot";

<ListGrid>
  <GridSlot state="past" num="01" title="…" body="…" />
  <GridSlot state="active" num="02" title="…" body="…" />
  <GridSlot state="ghost" num="03" title="…" body="…" />
</ListGrid>
```

States: `ghost` (dashed placeholder) · `active` (accent border + drop anim) · `past` (dimmed context)

### Split shell (index + module)

```tsx
<section className="lx-split-section">
  <div className="lx-split-rail"><span className="lx-split-index">02</span></div>
  <div className="lx-split-module">
    <div className="lx-split-rule" aria-hidden />
    <article className="lx-split-panel">
      <div className="lx-split-panel-main">…</div>
      <footer className="lx-split-foot">…</footer>
    </article>
  </div>
</section>
```

`lx-split-module` keeps **rule height = panel height**. Meta goes in `lx-split-foot`, not a side column.

## Spacing (mandatory tokens)

| Token | px | Use |
|-------|-----|-----|
| `--space-5` | 24 | Default inner gap |
| `--space-7` | 48 | Section separation |
| `--space-9` | 96 | Split column gap |
| `--stage-pad-x/y` | theme | SceneChrome padding |

**Do not** use arbitrary `margin: 18px` or `gap: 22px`.

## Chapter CSS rules

1. `layouts.css` is global — do not re-import.
2. Layout → shell classes or `GridSlot`.
3. Motion / demo → **`ch-*` prefix only** in `index.css`.
4. Never override `.lx-*` font-size.

## Reference chapter

Read `chapters/01-example/Example.tsx` — demonstrates cover → split → grid-3 → quote.

## Outline ↔ shell mapping

Outline steps use **`[intent: …]`** visual intent tags (see `references/OUTLINE-FORMAT.md`).
**Do not** put `[shell: lx-cover]` in outline — pick the shell here at build time:

```
outline:  step 1 (~15s) — hero headline [intent: hero opener]
build:    SceneChrome + lx-cover-body

outline:  step 2 (~20s) — three cases, one per click [intent: list-reveal]
build:    SceneChrome + ListGrid + GridSlot (1 active / step)
```

## Quality checklist (ui-ux-pro-max adapted)

- [ ] Every step uses `SceneChrome` + one shell
- [ ] Primary copy uses `lx-*` roles — no raw font-size
- [ ] Body text ≤ 42ch wide
- [ ] List items: one `GridSlot` active per step
- [ ] Icons: inline SVG — no emoji
- [ ] **No italic** — no `serif-it`, no `font-style: italic` (use `.display-en-soft`)
- [ ] Motion: `prefers-reduced-motion` respected (global)
- [ ] 50% browser zoom: hero + card core message still readable
