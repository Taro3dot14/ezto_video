# SKILL.md → LangGraph 代码对应关系

## 概述

本文件记录原始 `web-video-presentation` SKILL.md 工作流与 `ezto-agent` 项目中 LangGraph 实现代码的对应关系。

## 项目结构

```
ezto-agent/
├── app/
│   ├── api/                    # FastAPI 服务层
│   │   ├── server.py           # FastAPI app + CORS + lifespan
│   │   ├── routes.py           # 7 个 REST + SSE 端点
│   │   ├── models.py           # Pydantic 请求/响应模型
│   │   └── workflow_manager.py # 工作流生命周期管理
│   ├── runtime/                # LangGraph 运行时
│   │   ├── state.py            # VideoWorkflowState TypedDict
│   │   ├── interrupts.py       # 6 个 checkpoint interrupt 函数
│   │   ├── ref_loader.py       # 参考文档按阶段加载策略
│   │   ├── guards.py           # 4 个策略守卫
│   │   ├── artifact_manager.py # 工作区目录 + artifact 契约
│   │   └── tool_adapters.py    # shell/scaffold/npm/typecheck 审计适配器
│   ├── graph/                  # LangGraph 图定义
│   │   └── web_video.py        # 27 节点图（已实现）
│   ├── references/             # 从 SKILL 迁移的参考文档
│   │   ├── SKILL.md
│   │   ├── CHAPTER-CRAFT.md
│   │   ├── SCRIPT-STYLE.md
│   │   ├── OUTLINE-FORMAT.md
│   │   ├── THEMES.md
│   │   ├── AUDIO.md
│   │   ├── RECORDING.md
│   │   └── EXAMPLES/
│   ├── themes/                 # 从 SKILL 迁移的 23 个主题
│   │   ├── bauhaus-bold/
│   │   ├── blueprint/
│   │   └── ...
│   ├── templates/              # 从 SKILL 迁移的 Vite 脚手架模板
│   ├── scripts/                # 从 SKILL 迁移的脚本
│   │   └── scaffold.sh
│   └── docs/
│       ├── skill-flow-parity.md    # 流程固化文档（节点映射表详细版）
│       └── code-mapping.md         # 本文件
```

## 工作流阶段 → LangGraph 节点

| # | SKILL.md 原始步骤 | LangGraph 节点名 | interrupt | 守卫 | 参考文档 | 代码位置 |
|---|:---|---|---|---|---|---|
| 1 | 1.1 识别用户输入 | `wv_identify_input` | 否 | — | — | `graph/web_video.py` |
| 2 | 1.2 产出初稿 | `wv_prepare_source_files` | 否 | — | `SCRIPT-STYLE.md`, `OUTLINE-FORMAT.md` | `graph/web_video.py` |
| 3 | script 自检 | `wv_validate_script` | 否 | — | `SCRIPT-STYLE.md` | `graph/web_video.py` |
| 4 | script 修复 | `wv_repair_script` | 否 | — | `SCRIPT-STYLE.md` | `graph/web_video.py` |
| 5 | outline 自检 | `wv_validate_outline` | 否 | — | `OUTLINE-FORMAT.md` | `graph/web_video.py` |
| 6 | outline 修复 | `wv_repair_outline` | 否 | — | `OUTLINE-FORMAT.md` | `graph/web_video.py` |
| 7 | **Checkpoint Plan** | `wv_checkpoint_plan` | **是** | — | themes metadata | `graph/web_video.py` + `runtime/interrupts.py:28` |
| 8 | 2.1 脚手架 | `wv_scaffold_presentation` | 否 | `guard_not_skip_checkpoint(plan)` | — | `graph/web_video.py` |
| 9 | 删除 demo 章节 | `wv_remove_example_chapter` | 否 | `guard_not_skip_checkpoint(plan)` | — | `graph/web_video.py` |
| 10 | 2.2 第 1 章实现 | `wv_build_chapter_1` | 否 | `guard_chapter_refs_loaded`, `guard_chapter_1_not_parallel` | `CHAPTER-CRAFT.md` | `graph/web_video.py` |
| 11 | 第 1 章自检 | `wv_validate_chapter_1` | 否 | — | `CHAPTER-CRAFT.md` | `graph/web_video.py` |
| 12 | 第 1 章修复 | `wv_repair_chapter_1` | 否 | — | `CHAPTER-CRAFT.md` | `graph/web_video.py` |
| 13 | **第 1 章验收** | `wv_checkpoint_chapter_1` | **是** | — | — | `graph/web_video.py` + `runtime/interrupts.py:71` |
| 14 | 2.3 选择开发模式 | `wv_select_development_mode` | 否 | `guard_not_skip_checkpoint(ch1)` | — | `graph/web_video.py` |
| 15 | 2.4 第 N 章实现 | `wv_build_chapter_n` | 否 | `guard_chapter_refs_loaded` | `CHAPTER-CRAFT.md` (每次 reload) | `graph/web_video.py` |
| 16 | 第 N 章自检 | `wv_validate_chapter_n` | 否 | — | `CHAPTER-CRAFT.md` | `graph/web_video.py` |
| 17 | 第 N 章修复 | `wv_repair_chapter_n` | 否 | — | `CHAPTER-CRAFT.md` | `graph/web_video.py` |
| 18 | 递增章节索引 | `wv_increment_chapter_index` | 否 | — | — | `graph/web_video.py` |
| 19 | **第 N 章逐章验收** (模式 A) | `wv_checkpoint_chapter_n` | **是** | — | — | `graph/web_video.py` + `runtime/interrupts.py:94` |
| 20 | **剩余章节批量验收** (模式 B) | `wv_checkpoint_remaining_batch` | **是** | — | — | `graph/web_video.py` + `runtime/interrupts.py:106` |
| 21 | 2.5 STORAGE_KEY 检查 | `wv_transition_to_phase3` | 否 | `guard_not_skip_checkpoint(ch1)` | — | `graph/web_video.py` |
| 22 | **Checkpoint Audio** | `wv_checkpoint_audio` | **是** | — | — | `graph/web_video.py` + `runtime/interrupts.py:120` |
| 23 | 3.1 抽出 narrations | `wv_extract_narrations` | 否 | — | — | `graph/web_video.py` |
| 24 | **检查 segments** | `wv_checkpoint_audio_segments` | **是** | — | — | `graph/web_video.py` + `runtime/interrupts.py:139` |
| 25 | 3.2 合成音频 | `wv_synthesize_audio` | 否 | — | — | `graph/web_video.py` |
| 26 | 3.3 音频异常报告 | `wv_report_audio_anomalies` | 否 | — | — | `graph/web_video.py` |
| 27 | Phase 4 录屏指引 | `wv_recording_guidance` | 否 | — | — | `graph/web_video.py` |

### 条件边

| 源节点 | 条件 | 目标节点 |
|---|---|---|
| `wv_validate_script` | pass | `wv_validate_outline` |
| `wv_validate_script` | fail (≤3 次) | `wv_repair_script` |
| `wv_validate_script` | fail (>3 次) | `wv_validate_outline` (强制通过) |
| `wv_repair_script` | 总是 | `wv_validate_script` |
| `wv_validate_outline` | pass | `wv_checkpoint_plan` |
| `wv_validate_outline` | fail (≤3 次) | `wv_repair_outline` |
| `wv_validate_outline` | fail (>3 次) | `wv_checkpoint_plan` (强制通过) |
| `wv_repair_outline` | 总是 | `wv_validate_outline` |
| `wv_checkpoint_plan` | resume | `wv_scaffold_presentation` |
| `wv_validate_chapter_1` | pass | `wv_checkpoint_chapter_1` |
| `wv_validate_chapter_1` | fail (≤3 次) | `wv_repair_chapter_1` |
| `wv_validate_chapter_1` | fail (>3 次) | `wv_checkpoint_chapter_1` (强制通过) |
| `wv_repair_chapter_1` | 总是 | `wv_validate_chapter_1` |
| `wv_checkpoint_chapter_1` | resume | `wv_select_development_mode` |
| `wv_select_development_mode` | 还有章 | `wv_build_chapter_n` |
| `wv_select_development_mode` | 无剩余章 | `wv_transition_to_phase3` |
| `wv_validate_chapter_n` | pass, mode A | `wv_checkpoint_chapter_n` |
| `wv_validate_chapter_n` | pass, mode B/C, 还有章 | `wv_increment_chapter_index` |
| `wv_validate_chapter_n` | pass, mode B/C, 无剩余章 | `wv_checkpoint_remaining_batch` |
| `wv_validate_chapter_n` | fail (≤3 次) | `wv_repair_chapter_n` |
| `wv_validate_chapter_n` | fail (>3 次) | mode 路由 (强制通过) |
| `wv_repair_chapter_n` | 总是 | `wv_validate_chapter_n` |
| `wv_checkpoint_chapter_n` | 继续 & 还有章 | `wv_increment_chapter_index` |
| `wv_checkpoint_chapter_n` | 停止或无剩余章 | `wv_transition_to_phase3` |
| `wv_increment_chapter_index` | 还有章 | `wv_build_chapter_n` |
| `wv_increment_chapter_index` | 无剩余章 | `wv_transition_to_phase3` |
| `wv_checkpoint_audio` | yes | `wv_extract_narrations` |
| `wv_checkpoint_audio` | no | `wv_recording_guidance` |

## 中断 (Interrupt) 对应关系

SKILL.md 中有 6 个硬节点（必须停），每个对应一个 `interrupt()` 调用：

| SKILL.md 节点 | 中断函数 | type payload | 文件 |
|---|---|---|---|
| Checkpoint Plan — 一次对齐 5 件事 | `checkpoint_plan()` | `"checkpoint_plan"` | `app/runtime/interrupts.py:28` |
| 第 1 章强制验收 | `checkpoint_chapter_1()` | `"checkpoint_chapter_1"` | `app/runtime/interrupts.py:71` |
| 第 N 章逐章验收 (模式 A) | `checkpoint_chapter_n()` | `"checkpoint_chapter_n"` | `app/runtime/interrupts.py:94` |
| 剩余章节批量验收 (模式 B/C) | `checkpoint_remaining_batch()` | `"checkpoint_remaining_batch"` | `app/runtime/interrupts.py:106` |
| Checkpoint Audio — 是否合成音频 | `checkpoint_audio()` | `"checkpoint_audio"` | `app/runtime/interrupts.py:120` |
| 检查 audio-segments.json | `checkpoint_audio_segments()` | `"checkpoint_audio_segments"` | `app/runtime/interrupts.py:139` |

## 策略守卫 (Guard) 对应关系

| SKILL.md 规则 | 守卫函数 | 拦截场景 | 文件 |
|---|---|---|---|
| 每章实现前必须重读 CHAPTER-CRAFT.md | `guard_chapter_refs_loaded()` | 未加载 chapter ref 就进入 build 节点 | `app/runtime/guards.py:13` |
| 第 1 章不能被并行化 | `guard_chapter_1_not_parallel()` | parallel subgraph 中检测到 ch1 | `app/runtime/guards.py:29` |
| 禁止跳过 checkpoint | `guard_not_skip_checkpoint()` | checkpoint 未确认就进入后续节点 | `app/runtime/guards.py:45` |
| 禁止一次性加载所有 ref | `guard_no_bulk_ref_load()` | loaded_refs >= 4 个 | `app/runtime/guards.py:63` |

## 参考文档加载 (Ref Loader)

原 SKILL.md 规则：参考文档必须按阶段加载，不能启动时一次性读全部。

```python
# app/runtime/ref_loader.py
PHASE_REFS = {
    "phase1":   ["SCRIPT-STYLE.md", "OUTLINE-FORMAT.md"],
    "chapter":  ["CHAPTER-CRAFT.md"],
    "theme":    ["THEMES.md"],
    "audio":    ["AUDIO.md"],
    "recording": ["RECORDING.md"],
}
```

| 阶段 | 必读文档 | 调用 `require_ref_loaded` 的节点 |
|---|---|---|
| Phase 1 写稿 | `SCRIPT-STYLE.md` | `wv_prepare_source_files` |
| Phase 1 写 outline | `OUTLINE-FORMAT.md` | `wv_prepare_source_files` |
| Phase 2.1 脚手架 | `THEMES.md` (自定义主题时) | `wv_scaffold_presentation` |
| Phase 2.4 每章实现 | `CHAPTER-CRAFT.md` (每次 reload) | 每个 `wv_build_chapter_N` |
| Phase 3 音频合成 | `AUDIO.md` | `wv_extract_narrations`, `wv_synthesize_audio` |
| Phase 4 录屏 | `RECORDING.md` | `wv_recording_guidance` |

## Artifact 契约

原 SKILL.md 定义的工作目录结构，由 `artifact_manager.py` 强制执行：

```python
# app/runtime/artifact_manager.py
ARTIFACT_LAYOUT = {
    "article.md":          "article.md",
    "script.md":           "script.md",
    "outline.md":          "outline.md",
    "presentation":        "presentation",
    "audio-segments.json": "presentation/audio-segments.json",
    "public/audio":        "presentation/public/audio",
}
```

| 文件 | 创建节点 | 必须存在 | 合约位置 |
|---|---|---|---|
| `article.md` | `wv_prepare_source_files` | 仅用户给原文时 | `artifact_manager.py:32` |
| `script.md` | `wv_prepare_source_files` | 是 | `artifact_manager.py:33` |
| `outline.md` | `wv_prepare_source_files` | 是 | `artifact_manager.py:34` |
| `presentation/` | `wv_scaffold_presentation` | 是 (Phase 2 后) | `artifact_manager.py:35` |
| `audio-segments.json` | `wv_extract_narrations` | 仅 Phase 3 | `artifact_manager.py:37` |
| `public/audio/` | `wv_synthesize_audio` | 仅 Phase 3 | `artifact_manager.py:38` |

## API 端点 → 功能映射

| 端点 | 方法 | 功能 | 对应 SKILL.md | 文件 |
|---|---|---|---|---|
| `/health` | GET | 健康检查 | — | `server.py:51` |
| `/api/workflow/start` | POST | 启动新工作流 | Phase 1.1 入口 | `routes.py:60` |
| `/api/workflow/{id}/resume` | POST | 恢复中断 | 用户确认 checkpoint | `routes.py:83` |
| `/api/workflow/{id}` | GET | 查询状态 | 任何阶段 | `routes.py:109` |
| `/api/workflow/{id}/events` | GET | SSE 事件流 | 实时跟踪 | `routes.py:124` |
| `/api/workflow/{id}/artifacts` | GET | 列出构建产物 | — | `routes.py:172` |
| `/api/workflow/{id}/artifact/{path}` | GET | 读取文件内容 | — | `routes.py:185` |
| `/api/themes` | GET | 列出 23 个主题 | 对应 Checkpoint Plan 选主题 | `routes.py:201` |

## 主题系统

原 `skills/web-video-presentation/themes/` 中有 23 个主题。已迁移到 `app/themes/`。

每个主题包含：
- `theme.json` — 元数据 (`id`, `name`, `nameZh`, `description`, `bestFor`, `mood`, `preview`)
- `tokens.css` — CSS 自定义属性 (颜色、字体、排版 token)

主题加载路径：`app/api/workflow_manager.py` 中的 `_THEMES_DIR` 常量。

## 开发模式 A/B/C 的图拓扑

```
wv_select_development_mode
  ├── mode A ──→ [循环 ch2..N] build → validate → repair? → interrupt(chapter_n)
  ├── mode B ──→ [循环 ch2..N] build → validate → repair? → interrupt(remaining_batch)
  └── mode C ──→ [fan-out subgraph] build → validate → repair → [fan-in]
                                                              → interrupt(remaining_batch)
```

3 个模式共用 `wv_build_chapter_n`, `wv_validate_chapter_n`, `wv_repair_chapter_n` 节点，
但通过不同的**条件边**控制 interrupt 的位置和频次。

## 状态字段分组

`VideoWorkflowState` (定义于 `app/runtime/state.py`) 按职责分组：

| 分组 | 字段 | 用途 |
|---|---|---|
| identity | `thread_id`, `run_id` | 运行标识 |
| request | `user_request`, `language`, `input_type` | 用户输入 |
| flow control | `current_phase`, `current_node`, `completed_nodes`, `current_chapter_index`, `total_chapters`, `pending_interrupt` | 图执行状态 |
| refs | `required_refs`, `loaded_refs` | 参考文档加载 |
| artifacts | `workspace_root`, `artifact_paths`, `created_files`, `modified_files` | 文件系统 |
| decisions | `user_confirmations`, `selected_theme`, `selected_mode`, `synthesize_audio` | 用户选择 |
| validation | `validation_results`, `repair_history`, `errors` | 自检 + 修复 |
| tool policy | `allowed_tools`, `denied_tools`, `tool_calls` | 审计 |
| final | `final_summary` | 结束输出 |
