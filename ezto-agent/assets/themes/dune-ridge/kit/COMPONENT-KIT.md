# Dune Ridge - Theme Kit

> **Schema v2** - reusable `tk-*` components for this theme.
> Layout shells stay `lx-*` (LAYOUT-SYSTEM.md). Combine: `lx-split-panel tk-card`.

## Aesthetic

Gallery / architecture brochure - **hairline** borders, **paper-lift** shadow,
generous stage padding, muted clay accent. Quiet motion. Not chunky claymorphism.

## Stack

```
SceneChrome -> lx-* shell (layout)
           -> tk-* component (this kit - material)
           -> ch-* animation (chapter index.css only)
```

## Component vocabulary

| Class | Use for |
|-------|---------|
| `tk-card` | Main content panel - split/solo/cover foot |
| `tk-badge` | Status / kicker (uppercase mono, hairline) |
| `tk-chip` | Keyword tag (sentence case, soft sand fill) |
| `tk-button` | Decorative CTA (`--primary` = clay accent) |
| `tk-stat` | Large light-weight metric + mono label |
| `tk-icon-tile` | 64x64 SVG holder - **no emoji** |
| `tk-callout` | Tip / info block (`--tip` `--warn`) |
| `tk-progress` + `tk-progress__fill` | Slim sand progress bar |
| `tk-window` | Code/terminal chrome |
| `tk-slot` | GridSlot gallery skin - `<GridSlot className="tk-slot" ...>` |

## Per-step budget

- **1** primary `tk-card` (or shell panel with `tk-card`)
- **<= 3** auxiliary pieces (`tk-badge`, `tk-chip`, `tk-icon-tile`, `tk-stat`)
- **<= 1** `tk-button` (decorative)
- **1** dominant motion: `mot-tk-rise` | `mot-tk-pop` | existing `mot-*` (prefer slow)

## Patterns

### Split panel + card

```tsx
<article className="lx-split-panel tk-card">
  <span className="tk-badge tk-badge--accent lx-kicker">02 / SPACE</span>
  <h2 className="lx-title">...</h2>
  <p className="lx-body">...</p>
</article>
```

### List reveal slot

```tsx
<GridSlot
  className="tk-slot"
  state="active"
  num="02"
  title={<span className="lx-subtitle">...</span>}
  body={<span className="lx-body">...</span>}
/>
```

### Stat + icon row

```tsx
<div className="row" style={{ gap: "var(--space-6)", alignItems: "center" }}>
  <div className="tk-icon-tile mot-tk-pop">{/* inline SVG 26px */}</div>
  <div className="tk-stat">
    <span className="tk-stat__value">140</span>
    <span className="tk-stat__label">stage pad px</span>
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
  <pre className="tk-window__body">...</pre>
</div>
```

## Motion presets (theme-presets.css)

| Class | When |
|-------|------|
| `mot-tk-rise` | Card / panel entrance (preferred) |
| `mot-tk-pop` | Soft fade-in for badge / chip / icon |
| `mot-tk-press` | Button demo (add `is-pressed`) |

Prefer slow `mot-*` (hero mask, rule grow). **One dominant per step.** Avoid springy bounce.

## Rules

1. **Never** set raw `border-radius` / `box-shadow` on primary panels - use `tk-*`.
2. **Never** use emoji as icons - SVG inside `tk-icon-tile` only.
3. Typography roles: `.lx-hero` / `.lx-title` / `.lx-body` - no invented font-size.
4. Colors: `var(--text)`, `var(--accent)`, `var(--surface-*)` only - no hex in index.css.
5. Keep **restraint**: thin borders; avoid clay-style thick lifts or rainbow accents.
6. **Do not** put chapter_id / Cold Open / Hook on screen as kicker copy.

## Anti-patterns

- Nested `tk-card` x 3
- `tk-button` as real navigation
- Purple gradients / glass neon (NO_AI_SLOP)
- Chunky 4px clay borders (wrong family - use clay-warm for that)
- Italic display type
- Busy surface patterns / vignettes (breaks dune purity)
