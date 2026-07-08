# Motion Template System

> **First principle:** Layout = `lx-*` shells (see `layouts/LAYOUT-SYSTEM.md`).
> Motion = **one dominant preset per step** + optional accompaniment.
> Chapter `index.css` adds **`ch-*` only** when a preset needs content-specific tweaks.

## Stack

```
SceneChrome → lx-* shell → motion preset (mot-*) → optional ch-* override
```

## Build order (per step)

1. Pick **one shell** (`lx-cover`, `lx-split`, `ListGrid`+`GridSlot`, …)
2. Pick **one dominant** motion preset for that step
3. Optional: **one accompaniment** (rule-grow, caption-rise)
4. Wire with `MaskReveal` / global classes from `animations.css`
5. Custom keyframes → **`ch-*` in index.css only**

## Dominant presets (pick ONE per step)

| Preset class | Use when | Pair with shell | Implementation |
|--------------|----------|-----------------|----------------|
| `mot-hero-mask` | Hero / title reveal | cover, quote, split main | `<MaskReveal show duration={900}>` on `.lx-hero` / `.lx-title` |
| `mot-hero-blur` | Cinematic title sharpen | cover, solo | `.mot-hero-blur` on headline wrapper |
| `mot-stamp-drop` | Badge / stamp / “砸下” | solo, grid slot | `.mot-stamp-drop` on accent label |
| `mot-type-mono` | Terminal typing | terminal, split foot | `.mot-type-mono` + caret blink |
| `mot-hard-cut` | Bauhaus / Swiss block enter | cover, stack | `.mot-hard-cut` — no fade |
| `mot-slot-fill` | List item activates | grid-3 + GridSlot | `GridSlot state="active"` (uses `lx-slot-drop`) |

## Accompaniment (optional, max ONE)

| Class | Effect |
|-------|--------|
| `mot-rule-grow` | Accent rule scaleX — add `.rule-grow.in` or use preset |
| `mot-caption-rise` | Kicker/caption delayed rise |
| `mot-delay-200` / `mot-delay-400` | Stagger helper on accompaniment only |

## Intent → shell + motion (outline `[intent: …]`)

| Intent | Shell | Dominant motion |
|--------|-------|-----------------|
| hero opener | `lx-cover-body` | `mot-hero-mask` or `mot-hero-blur` |
| solo reveal | `lx-solo` | `mot-stamp-drop` + MaskReveal on image |
| list-reveal | `ListGrid` + `GridSlot` | `mot-slot-fill` |
| quote close | `lx-quote-body` | `mot-hero-mask` + `mot-rule-grow` |
| intro / transition | `lx-stack` | `mot-hero-mask` on title only |
| terminal / demo | `lx-terminal` | `mot-type-mono` |

## Theme duration (use tokens — never hardcode ms in copy)

| Token | Typical use |
|-------|-------------|
| `--dur-quick` | Micro accent (200–400ms themes) |
| `--dur-base` | Default entrances |
| `--dur-slow` | Hero / mask reveals |
| `--dur-cinematic` | Full-screen takeover |
| `--ease-quart` / `--ease-expo` | Enter easing |

Read active values from `src/styles/tokens.css` after scaffold.

## Anti-patterns (HARD FAIL — reviewer / NO_AI_SLOP)

- **Same entrance on every step** in one chapter (all fade / all blur)
- **>2 animated elements** fighting on one step
- **`infinite` animation** on primary copy or hero
- **Ken burns / pulse on every step** — at most one subtle instance per chapter
- **Raw `@keyframes` in index.css** without `ch-*` prefix
- **Inventing layout in index.css** — motion only

## Global primitives (already imported — do NOT re-read)

From `src/styles/animations.css`:

- `.mask-reveal` + `<MaskReveal>` component
- `.rule-grow` — accent line grow
- `@keyframes rise-in`, `scale-in`, `pop-in`, `letter-rise`

From `src/motion/presets.css`:

- `.mot-*` preset hooks (this file)

## Reference code

- Layout lab: `chapters/01-example/Example.tsx` (MaskReveal on cover/split/quote)
- Motion CSS: `src/motion/presets.css`
- Slot drop: `layouts/layouts.css` → `@keyframes lx-slot-drop`

## Quality checklist (each step)

- [ ] One shell + one dominant motion
- [ ] Animation duration ≤ step narration length (Auto mode cuts on audio end)
- [ ] Uses theme `--dur-*` / `--ease-*`
- [ ] `prefers-reduced-motion` respected (global in animations.css)
- [ ] Different steps use **different** dominant motions when possible
