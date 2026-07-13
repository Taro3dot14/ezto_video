# Clay Warm · Theme Kit

> **Schema v2** — reusable `tk-*` components for this theme.
> Layout shells stay `lx-*` (LAYOUT-SYSTEM.md). Combine: `lx-split-panel tk-card`.

## Stack

```
SceneChrome → lx-* shell (layout)
           → tk-* component (this kit — material)
           → ch-* animation (chapter index.css only)
```

## Component vocabulary

| Class | Use for |
|-------|---------|
| `tk-card` | Main content panel — split/solo/cover foot |
| `tk-badge` | Status / kicker pill (uppercase mono) |
| `tk-chip` | Keyword tag (sentence case) |
| `tk-button` | Decorative CTA (`--primary` variant) |
| `tk-stat` | Big metric + label |
| `tk-icon-tile` | 64×64 SVG holder — **no emoji** |
| `tk-callout` | Tip / info block (`--tip` `--warn`) |
| `tk-progress` + `tk-progress__fill` | Chunky progress bar |
| `tk-window` | Code/terminal chrome (replaces plain lx-terminal bar) |
| `tk-slot` | GridSlot clay skin — add to `<GridSlot className="tk-slot" …>` |

## Per-step budget

- **1** primary `tk-card` (or shell panel with `tk-card`)
- **≤ 3** auxiliary pieces (`tk-badge`, `tk-chip`, `tk-icon-tile`, `tk-stat`)
- **≤ 1** `tk-button` (decorative)
- **1** dominant motion: `mot-tk-pop` | `mot-tk-rise` | existing `mot-*`

## Patterns

### Split panel + card

```tsx
<article className="lx-split-panel tk-card">
  <span className="tk-badge tk-badge--accent lx-kicker">Step 02</span>
  <h2 className="lx-title">…</h2>
  <p className="lx-body">…</p>
</article>
```

### List reveal slot

```tsx
<GridSlot
  className="tk-slot"
  state="active"
  num="02"
  title={<span className="lx-subtitle">…</span>}
  body={<span className="lx-body">…</span>}
/>
```

### Stat + icon row

```tsx
<div className="row" style={{ gap: "var(--space-6)", alignItems: "center" }}>
  <div className="tk-icon-tile mot-tk-pop">{/* inline SVG 28px */}</div>
  <div className="tk-stat">
    <span className="tk-stat__value">78%</span>
    <span className="tk-stat__label">completion rate</span>
  </div>
</div>
```

### Terminal window

```tsx
<div className="tk-window">
  <div className="tk-window__bar">
    <span className="tk-window__dot tk-window__dot--close" />
    <span className="tk-window__dot tk-window__dot--min" />
    <span className="tk-window__dot tk-window__dot--max" />
  </div>
  <pre className="tk-window__body">…</pre>
</div>
```

## Motion presets (theme-presets.css)

| Class | When |
|-------|------|
| `mot-tk-pop` | Badge, icon tile, chip entrance |
| `mot-tk-rise` | Card / panel entrance |
| `mot-tk-press` | Button demo (add `is-pressed` for held state) |

Pair with existing `mot-hero-mask`, `mot-slot-fill` — **one dominant per step**.

## Rules

1. **Never** set raw `border-radius` / `box-shadow` on primary copy containers — use `tk-*`.
2. **Never** use emoji as icons — SVG inside `tk-icon-tile` only.
3. Typography roles: `.lx-hero` / `.lx-title` / `.lx-body` — no invented font-size.
4. Colors: `var(--text)`, `var(--accent)`, `var(--surface-*)` only — no hex in index.css.
5. Main panels: `border-radius` ≥ `var(--tk-r-md)` (24px).

## Anti-patterns

- ❌ Nested `tk-card` × 3
- ❌ `tk-button` as real navigation (decorative only)
- ❌ Purple gradients / thin glass cards (NO_AI_SLOP)
- ❌ Italic display type
