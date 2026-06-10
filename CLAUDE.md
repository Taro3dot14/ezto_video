# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This repo contains the `web-video-presentation` **Claude Code skill** — a methodology-driven tool that turns articles/scripts into click-driven 16:9 web presentations (Vite + React + TS) that can be screen-recorded as cinematic videos. It is not a standalone app; it is a promptable skill meant to be loaded into an agent session.

```text
skills/web-video-presentation/
├── SKILL.md                    # Entry point — full workflow definition
├── README.md / README.zh-CN.md
├── manifest.json               # Skill metadata (name, compat, version)
├── references/
│   ├── CHAPTER-CRAFT.md        # Chapter implementation rules + self-check
│   ├── OUTLINE-FORMAT.md       # Outline file format spec
│   ├── SCRIPT-STYLE.md         # Article-to-narration rewrite rules
│   ├── THEMES.md               # Theme token contract + creation guide
│   ├── AUDIO.md                # Audio synthesis workflow
│   └── RECORDING.md            # Screen recording guide
├── scripts/
│   └── scaffold.sh             # One-command project scaffold
├── templates/
│   ├── index.html
│   ├── vite.config.ts
│   ├── scripts/
│   │   ├── extract-narrations.ts     # Scan narrations → audio-segments.json
│   │   ├── synthesize-audio.sh       # Provider-agnostic TTS runner
│   │   └── tts-providers/            # 1 file = 1 TTS backend (minimax, openai)
│   └── src/
│       ├── main.tsx                  # React entry point
│       ├── App.tsx                   # Root: stepper + stage + audio + auto-mode
│       ├── hooks/
│       │   ├── useStepper.ts         # Global (chapter, step) cursor + keyboard nav
│       │   ├── useStageScale.ts      # Scale 1920×1080 to viewport
│       │   ├── useAudioPlayer.ts     # Per-step audio playback
│       │   └── useAutoMode.ts        # manual/audio/auto mode state machine
│       ├── components/
│       │   ├── Stage.tsx             # 16:9 click-to-advance stage
│       │   ├── MaskReveal.tsx        # Clip-path text wipe component
│       │   ├── ProgressBar.tsx       # Hidden-until-hover chapter progress
│       │   ├── AutoStartGate.tsx     # Space-to-start gate for auto mode
│       │   └── AutoToggle.tsx        # M-key mode toggle UI
│       ├── registry/
│       │   ├── types.ts              # ChapterDef, Narration, ChapterStepProps
│       │   └── chapters.ts           # Chapter registry — order of presentation
│       ├── styles/
│       │   ├── base.css              # Design system, primitives, token wiring
│       │   ├── animations.css        # Theme-agnostic motion vocabulary
│       │   └── fonts.css             # Google Fonts for built-in themes
│       └── chapters/
│           └── 01-example/           # Demo chapter (deleted in real projects)
└── themes/
    ├── midnight-press/              # 23 themes, each with theme.json + tokens.css
    ├── paper-press/
    └── ...
```

## Architecture

### Core Model

- **Fixed 16:9 stage**: Content is authored at 1920×1080, then `transform: scale()` fits the viewport. No responsive breakpoints.
- **Global `(chapter, step)` cursor**: A single useState-based stepper drives everything. Chapters are pure functions of `step`. No timers, no imperative state.
- **`narrations.ts` is the single source of truth**: Each chapter has a `narrations` array. Its length === the number of steps. Audio synthesis and auto-advance mode both derive from this — keeps step count, visuals, and audio in sync.
- **Three playback modes** (synced to URL): `manual` (click to advance), `audio` (audio plays per step, click to advance), `auto` (audio plays + auto-advances on `ended` event).
- **Theme token system**: Colors and fonts come from CSS custom properties. Chapters never hardcode hex/color names/font families. 23 built-in themes.

### Key Constraints

- One step, one idea — each step owns the full screen (`if (step === N) return <Scene />`).
- Hidden chrome — progress bar is hover-only, no header/footer/page numbers.
- Content-driven animation — find the intrinsic motion of the content first; entrance animations are the fallback.
- Multi-point reveals must be 1-item-per-step (no staggering 3 items in one step).
- Animation duration must be ≤ narration duration (auto mode advances on audio `ended` with no minimum hold).

### Scaffold Flow

```bash
# Create a presentation project with a selected theme
bash skills/web-video-presentation/scripts/scaffold.sh ./presentation --theme=midnight-press
# List available themes
bash skills/web-video-presentation/scripts/scaffold.sh --list-themes
```

The scaffold copies template files, installs dependencies, copies theme tokens, and runs `npx tsc --noEmit`.

## Key Development Commands

```bash
# Inside a scaffolded project (not in this repo root):
npm run dev              # Start dev server (default :5174)
npx tsc --noEmit         # TypeScript type check (required per-chapter self-check)
npm run extract-narrations  # Scan all chapters → audio-segments.json
npm run synthesize-audio     # Synthesize audio (requires TTS provider)
```

## Workflow Phases (from SKILL.md)

1. **Content writing** (Phase 1): article → `script.md` (narration) + `outline.md` (chapter plan)
2. **Checkpoint Plan**: align script, outline, theme, assets, dev mode with user
3. **Web development** (Phase 2): scaffold → chapter 1 (mandatory full version + user review) → chapters 2-N (sequential or parallel)
4. **Checkpoint Audio**: ask user if they want AI narration
5. **Audio synthesis** (Phase 3): optional TTS (minimax, OpenAI, or custom provider)
6. **Recording** (Phase 4): screen record with `?auto=1` for one-take capture

### Hard Self-Check Protocol

After each deliverable (`script.md`, `outline.md`, each chapter), run the corresponding self-check (prefer agent teams for isolation, then subagent, then self-check) and fix failures before reporting to user.

## When Working With This Skill

- **SKILL.md is the single entry point** — read it before anything else. It defines the full workflow, checkpoints, and file conventions.
- **CHAPTER-CRAFT.md is the single must-read for chapter implementation** — covers all rules (principles, content-driven animation, anti-AI patterns, code constraints, self-check).
- When implementing a chapter, always read the corresponding section in `article.md` for visual details (dual-source principle: pacing follows `script.md`, visual density comes from `article.md`).
- Themes live in `themes/<id>/` — each has a `theme.json` (metadata + mood) and `tokens.css` (CSS custom properties). Theme selection happens at Checkpoint Plan.
- The `scaffold.sh` script is the only supported way to create a project — don't manually create Vite projects for this workflow.
