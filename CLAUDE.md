# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This repo contains **two things that coexist**:

1. **`skills/web-video-presentation/`** — the original Claude Code skill that turns articles/scripts into click-driven 16:9 web presentations (Vite + React + TS). This is the *methodology spec* for the agent workflow below.

2. **`ezto-agent/`** — a LangGraph-based backend (Python + FastAPI) that **automates the original skill's workflow** as a deterministic state machine. A React frontend (`ezto-agent/frontend/`) provides the UI.

The core idea: what was once a promptable Claude Code skill is now a 22-node LangGraph graph with checkpoint interrupts, validate-repair loops, and development-mode branching — served via a FastAPI + React stack.

## Architecture

### LangGraph Workflow (22 nodes, 4 phases)

The graph in `ezto-agent/app/graph/web_video.py` mirrors the original SKILL.md methodology:

```
Phase 1 (Content Writing):
  wv_identify_input → wv_prepare_source_files → wv_validate_script → (repair loop)
  → wv_validate_outline → (repair loop) → wv_checkpoint_plan [INTERRUPT]

Phase 2 (Web Development):
  wv_scaffold_presentation → wv_remove_example_chapter
  → wv_build_chapter_1 → validate/repair → wv_checkpoint_chapter_1 [INTERRUPT]
  → wv_build_chapter_n → validate/repair → checkpoint [INTERRUPT per mode]

Phase 3 (Audio Synthesis, optional):
  wv_checkpoint_audio [INTERRUPT] → wv_extract_narrations
  → wv_checkpoint_audio_segments [INTERRUPT] → wv_synthesize_audio

Phase 4 (Recording):
  wv_recording_guidance → END
```

Key design points:
- **6 checkpoint interrupts** where the graph pauses for user confirmation (plan, chapter 1, chapter N, batch, audio, segments)
- **Validate-repair loops** with 3-retry max for script.md, outline.md, chapters
- **3 development modes**: A = sequential+per-chapter interrupt, B = sequential+batch, C = parallel subgraphs
- **Reference loading policy**: refs loaded per-phase, not all at startup (enforced by `guards.py`)
- **Artifact contract**: files must be created at expected paths (enforced by `artifact_manager.py`)

### Backend Stack (ezto-agent/)

```
ezto-agent/
├── app/
│   ├── api/                  # FastAPI server, routes, models, workflow manager
│   │   ├── server.py         # Entry: uvicorn app.api.server:app --port 8001
│   │   ├── routes.py         # REST endpoints + SSE events
│   │   ├── models.py         # Pydantic request/response models
│   │   └── workflow_manager.py    # LangGraph orchestration
│   ├── graph/
│   │   └── web_video.py      # 22-node StateGraph definition
│   ├── runtime/
│   │   ├── state.py          # VideoWorkflowState (TypedDict)
│   │   ├── interrupts.py     # Checkpoint → LangGraph interrupt mapping
│   │   ├── artifact_manager.py    # Path contracts
│   │   ├── ref_loader.py     # Per-phase reference loading policy
│   │   ├── tool_adapters.py  # Shell, scaffold, npm, typecheck adapters
│   │   └── guards.py         # Policy violation guards
│   ├── core/
│   │   ├── __init__.py       # Settings (env-based via pydantic-settings)
│   │   ├── llm.py            # DeepSeek chat/stream client (OpenAI-compatible)
│   │   └── logger.py         # Console + file + LLM interaction logging
│   └── references/           # Phase reference docs (copied from skills/)
├── frontend/                 # React + Vite + TS workflow UI
│   └── src/
│       ├── pages/            # HomePage, NewProjectPage, WorkflowPage
│       ├── components/       # CheckpointPlanView, ChapterReviewView, etc.
│       └── api/client.ts     # Backend API + SSE helpers
└── tests/
    └── flow_parity/          # Golden trace and parity tests
```

## Key Development Commands

### Backend (ezto-agent/)

```bash
cd ezto-agent

# Setup (WSL conda)
bash setup_wsl.sh

# Start dev server
conda activate py312  # or ezto
uvicorn app.api.server:app --reload --port 8001

# Run tests
pytest
```

### Frontend (ezto-agent/frontend/)

```bash
cd ezto-agent/frontend
npm install
npm run dev          # Vite dev server (default :5173)
npm run build        # Production build
```

### Inside a scaffolded presentation project

```bash
cd presentation
npm run dev              # Start presentation preview (default :5202)
npx tsc --noEmit         # TypeScript type check
npm run extract-narrations  # Scan chapters → audio-segments.json
npm run synthesize-audio     # TTS synthesis
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/workflow/start` | Start new workflow |
| POST | `/api/workflow/{id}/resume` | Resume interrupted workflow |
| GET | `/api/workflow/{id}` | Get current state |
| GET | `/api/workflow/{id}/events` | SSE event stream |
| GET | `/api/workflow/{id}/artifacts` | List output files |
| GET | `/api/workflow/{id}/artifact/{path}` | Read output file content |
| GET | `/api/themes` | List 23 available themes |
| GET | `/health` | Health check |

## Core Model (Original Skill)

Used when building presentation chapters:

- **Fixed 16:9 stage**: Content at 1920×1080, `transform: scale()` to viewport
- **Global `(chapter, step)` cursor**: Single useState stepper, chapters are pure functions of `step`
- **`narrations.ts` is source of truth**: Array length === number of steps
- **3 playback modes**: `manual` (click), `audio` (play + click), `auto` (play + auto-advance)
- **Theme token system**: 23 themes via CSS custom properties, no hardcoded colors/fonts

### Key Constraints

- One step, one idea — each step owns full screen (`if (step === N) return <Scene />`)
- Hidden chrome — progress bar is hover-only, no header/footer/page numbers
- Content-driven animation before entrance animations
- Multi-point reveals must be 1-item-per-step
- Animation duration ≤ narration duration (auto mode advances on `ended`)

## When Working With This Repo

- **For changes to the workflow automation** (LangGraph nodes, API, frontend): the source of truth is `skills/web-video-presentation/SKILL.md` — the LangGraph must maintain flow parity with it
- **For changes to the presentation templates**: edit `skills/web-video-presentation/templates/` and `skills/web-video-presentation/themes/`
- **REFERENCES.md files** in `skills/` are the originals; `ezto-agent/app/references/` are copies used at runtime
- **CHAPTER-CRAFT.md** must be re-read for each chapter build (not cached once)
- The `scaffold.sh` script is the only supported way to create a presentation project
- Checkpoint interrupts cannot be skipped — the graph enforces user confirmation at 6 hard stops
