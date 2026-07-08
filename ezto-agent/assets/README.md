# ezto-agent/assets — Design System Source of Truth

> **First principle:** This product is a **recorded 1920×1080 click-driven video**,
> not a responsive website. Assets encode **what must stay fixed** vs **what agents may vary**.

## Three layers

```
references/     Methodology specs (CHAPTER-CRAFT, OUTLINE, EXAMPLES anchors)
templates/      Runtime scaffold — Stage, layouts, components, 01-example
themes/         23 visual identities — colors, fonts, motion mood (tokens.css)
```

| Layer | Owns | Does NOT own |
|-------|------|--------------|
| **themes/** | Palette, font families, `--stage-pad-*`, motion `--dur-*`, card personality | Layout structure, step content |
| **templates/** | 16:9 stage, layout shells (`lx-*`), typography roles, primitives | Chapter copy, demos |
| **references/** | Workflow rules, outline format, example anchors | Generated chapter code |

## Layout Shell System (templates)

Chapters **must not invent typography or spacing**. Use:

1. `<SceneChrome>` — masthead + stage padding
2. One shell per step — `lx-cover`, `lx-split`, `lx-solo`, `lx-grid-3`, `lx-grid-2`, `lx-quote`, …
3. Typography roles — `.lx-hero`, `.lx-body`, `.lx-caption`
4. Chapter CSS — **`ch-*` animation overrides**; motion presets — **`mot-*`** in `motion/presets.css`

Full spec: `templates/src/layouts/LAYOUT-SYSTEM.md`

## Theme swap

Scaffold copies one theme → `presentation/src/styles/tokens.css`.  
Chapters use semantic tokens only — **zero hex in chapter CSS**.  
During workflow **preview** (after scaffold), the UI can swap any built-in theme by overwriting `tokens.css` — no rebuild required.

## Agent reading order

1. `references/CHAPTER-CRAFT.md` (via read_reference)
2. `read_chapter_context` → article + 01-example + LAYOUT-SYSTEM.md + **MOTION-SYSTEM.md + presets.css**
3. Pick shell per outline step → pick **mot-*** dominant motion → `ch-*` overrides if needed

## ui-ux-pro-max alignment (adapted for fixed canvas)

| Web UI rule | Video presentation adaptation |
|-------------|-------------------------------|
| Modular type scale | Locked in `layouts.css` (`lx-*` roles) |
| max-w-prose (~65ch) | `lx-body` max 42ch, `lx-hero` max 14ch |
| No emoji icons | SVG + CSS shapes (NO_AI_SLOP) |
| 150–300ms transitions | `--dur-quick` / `--dur-base` from theme |
| prefers-reduced-motion | `animations.css` + layout transitions |
| Consistent spacing | `--space-*` scale only — no magic px gaps |

## Directory map

```
assets/
├── README.md                 ← this file
├── references/               → copied to harness at runtime
│   ├── CHAPTER-CRAFT.md
│   ├── EXAMPLES/             structural anchors (map → lx-* shells)
│   └── THEMES.md
├── templates/                → scaffold.sh copies into presentation/
│   └── src/
│       ├── layouts/          Layout Shell System
│       ├── motion/           Motion Template System (MOTION-SYSTEM.md, presets.css)
│       ├── components/       Stage, SceneChrome, GridSlot, MaskReveal
│       ├── styles/           base.css, animations.css, fonts.css
│       └── chapters/01-example/
└── themes/<id>/              tokens.css + theme.json per theme
```
