# ezto-video 基于 LangGraph 的原流程完全复现重构规划

> 版本：v2 - Flow-Parity First  
> 目标仓库：`ezto-video`  
> 规划原则：**先 100% 复现原 `web-video-presentation` 流程，再考虑增强。**  
> 重要修正：本版不再把原 SKILL.md 仅作为"业务语义参考"，而是把 SKILL.md 中的流程、硬节点、强制读取、降级模式、自检协议、输出契约都映射为 LangGraph 节点和状态转移。

---

## 1. 背景与目标

`ezto-video` 当前不是一个传统后端服务，而是一个 Agent Skill 项目。仓库中，技能位于 `skills/web-video-presentation` 下，以 `SKILL.md` 作为 Agent-facing spec，并配套 `manifest.json`、README、references、scripts、templates、assets 等资源。

本次重构目标：

1. **完全复现原 Skill 的执行流程**
   - 原 Skill 规定的阶段必须保留。
   - 原 Skill 规定的 checkpoint 必须保留。
   - 原 Skill 规定的"先读取 references 再处理"必须保留。
   - 原 Skill 的禁止行为必须保留。
   - 原 Skill 的输出目录、命名规则、文件契约必须保留。

2. **用 LangGraph 把原 Skill 流程显式状态机化**
   - 原来写在 Markdown 里的流程，变成 `StateGraph` 节点。
   - 原来的"必须停下来等用户确认"，变成 LangGraph `interrupt()`。
   - 原来的"完成后必须自检 → 修复 → 再汇报"，变成 `validate -> repair -> revalidate` 循环。
   - 原来的模式分支（Mode A / B / C），变成条件边。
   - 原来的子任务并行（第 2~N 章并行开发），变成子图 fan-out。

3. **增强只做承载层，不改业务流程**
   - 状态持久化、线程恢复、日志追踪、隔离、artifact 管理可以加入。
   - 但这些能力不能改变原 Skill 的行为顺序。
   - 增强必须服从 Flow Parity，不允许替代原 Skill 的 checkpoint 和自检逻辑。

---

## 2. 总体原则：Flow Parity First

### 2.1 核心判断

本次重构采用：

```text
原 SKILL.md = 流程真相源
LangGraph = 流程执行器
```

不能采用：

```text
原 SKILL.md = 灵感来源
LangGraph = 新流程设计器
```

也就是说，LangGraph 不负责"优化"原流程，而负责**逐节点复现**原流程。

---

### 2.2 不允许改变的内容

| 类别 | 原 Skill 行为 | LangGraph 迁移要求 |
|---|---|---|
| 阶段顺序 | `SKILL.md` 中定义的 Phase / Step 顺序 | 必须一一映射为节点和边 |
| 用户确认 | 原文标注 "必须停""Checkpoint""硬节点" | 必须实现为 `interrupt()` |
| 强制读取 | 原文要求先读某 references 文件 | 必须设置 `required_refs` 并在节点前校验 |
| 自检协议 | 自检 → 修复 → 再汇报 | 必须实现 validate-repair loop |
| 输出路径 | 原文规定的文件目录和命名 | 必须由 ArtifactManager 固化 |
| 模式分支 | 开发模式 A / B / C | 必须按原条件分叉 |
| 禁止行为 | 不允许跳过 references | 必须由 Guard 节点拦截 |

### 2.3 允许新增的内容

允许新增，但不能改变原 Skill 外部行为：

| 新增能力 | 作用 | 是否影响原流程 |
|---|---|---|
| thread_id | 用于恢复同一任务 | 不影响 |
| checkpoint persistence | 用于中断恢复和失败重试 | 不影响 |
| run trace | 记录节点执行路径 | 不影响 |
| artifact index | 管理产物路径和版本 | 不影响 |
| audit log | 记录工具调用、文件写入、用户确认 | 不影响 |
| regression tests | 保证复现原流程 | 不影响 |

---

## 3. 当前 Skill 资产盘点

当前仓库中包含 1 个核心 Skill：

| Skill | 目录 | 原用途 | LangGraph 子图 |
|---|---|---|---|
| web-video-presentation | `skills/web-video-presentation` | 将文章/口播稿做成点击驱动的网页视频演示，可选音频合成 | `WebVideoPresentationGraph` |

---

## 4. 目标架构总览

### 4.1 完整项目结构

```text
ezto-agent/
├── app/
│   ├── api/                         # FastAPI 后端
│   │   ├── server.py                # FastAPI app 入口
│   │   ├── routes.py                # REST 路由
│   │   ├── models.py                # Pydantic 模型
│   │   └── workflow_manager.py      # LangGraph 编排
│   ├── graph/
│   │   └── web_video.py             # 完全复现的 LangGraph 图
│   ├── runtime/
│   │   ├── state.py                 # VideoWorkflowState
│   │   ├── interrupts.py            # checkpoint → interrupt
│   │   ├── artifact_manager.py      # 输出路径契约
│   │   ├── ref_loader.py            # references 强制读取
│   │   ├── tool_adapters.py         # Shell/Read/Scaffold/NPM 封装
│   │   └── guards.py                # 禁止行为拦截
│   └── observability/
│       ├── trace_logger.py
│       └── audit_logger.py
│
├── frontend/                        # React + Vite + TS 前端
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/client.ts
│   │   ├── pages/
│   │   ├── components/
│   │   └── styles/
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── skills/                           # 原 spec 资产 (只读输入)
│   └── web-video-presentation/
│
├── workspace/{thread_id}/            # 运行时产出
├── tests/
└── pyproject.toml
```

---

## 5. 系统架构

### 5.1 三层架构

```text
┌─────────────────────────────────────────────────┐
│                   前端 (Frontend)                  │
│   React + Vite + TypeScript                      │
│   路由: /submit /checkpoint-plan /chapters /    │
│         /checkpoint-audio /progress              │
│   通过 REST API + SSE 与后端通信                  │
└──────────────────┬──────────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────────────┐
│                后端 API (Backend)                  │
│   FastAPI + Uvicorn                               │
│   REST 端点: POST /workflow/start                │
│              POST /workflow/resume                │
│              GET  /workflow/{id}/state            │
│              GET  /workflow/{id}/events (SSE)     │
│              POST /workflow/{id}/cancel           │
│   功能: 请求路由 / 中断管理 / 状态查询            │
└──────────────────┬──────────────────────────────┘
                   │ invoke / interrupt / resume
┌──────────────────▼──────────────────────────────┐
│               LangGraph 引擎                       │
│   VideoWorkflowGraph                              │
│   节点: wv_identify_input, wv_validate_script,   │
│         wv_checkpoint_plan, wv_build_chapter_1,  │
│         ... (20+ 节点)                            │
│   interrupt() → 等待用户确认 → resume()          │
│   持久化: Thread(checkpointer)                    │
└─────────────────────────────────────────────────┘
```

### 5.2 交互流程

```
User                 Frontend               Backend API           LangGraph
 │                      │                      │                     │
 │ 提交文章/口播稿        │                      │                     │
 │─────────────────────► │  POST /workflow/start │                     │
 │                      │─────────────────────►│                     │
 │                      │                      │  invoke()           │
 │                      │                      │────────────────────►│
 │                      │                      │  Phase-1 nodes      │
 │                      │                      │  ...                │
 │                      │                      │  interrupt()        │
 │                      │◄─── 200 {thread_id} ──┤◄────────────────────│
 │                      │                      │                     │
 │ 轮询或 SSE 获取状态   │                      │                     │
 │◄─────────────────────│                      │                     │
 │                      │ GET /workflow/{id}/state                    │
 │                      │─────────────────────►│                     │
 │                      │◄─── {current_node,   │                     │
 │                      │       interrupt_data} │                     │
 │                      │                      │                     │
 │ 用户确认(选主题等)     │                      │                     │
 │─────────────────────► │ POST /workflow/resume│                     │
 │                      │─────────────────────►│  Command(resume)    │
 │                      │                      │────────────────────►│
 │                      │                      │  继续执行下一节点    │
 │                      │                      │  ...                │
 │                      │                      │  下一个 interrupt   │
 │                      │◄─────────────────────│◄────────────────────│
```

---

## 6. 统一状态设计

### 5.1 `VideoWorkflowState`

```python
class VideoWorkflowState(TypedDict):
    # identity
    thread_id: str
    run_id: str

    # request
    user_request: str
    language: str

    # flow
    current_phase: str
    current_node: str
    next_node: str | None
    completed_nodes: list[str]
    pending_interrupt: dict | None

    # skill source of truth
    skill_root: str
    skill_manifest: dict
    skill_md_path: str
    required_refs: list[str]
    loaded_refs: list[str]

    # artifacts
    workspace_root: str
    artifact_paths: dict
    created_files: list[str]
    modified_files: list[str]

    # user decisions
    user_confirmations: dict
    selected_mode: str | None          # A / B / C
    selected_theme: str | None

    # validation
    validation_results: list[dict]
    repair_history: list[dict]
    errors: list[dict]

    # tool policy
    allowed_tools: list[str]
    denied_tools: list[str]
    tool_calls: list[dict]

    # final
    final_summary: str | None
```

---

### 5.2 状态持久化要求

每个 LangGraph 运行必须有稳定的 `thread_id`：

```python
config = {
    "configurable": {
        "thread_id": thread_id
    }
}
```

原因：

- 原 Skill 有大量"必须停下来等用户确认"的硬节点。
- 中断后必须能从同一个节点恢复。
- 用户编辑文件或确认后，图必须继续原流程，而不是重新开始。
- 并行 subgraph 的执行状态也需要可追踪。

---

## 6. 原 Skill 流程完全复现方案

### 6.1 原流程摘要

原 Skill 的核心流程是：

```text
Phase 1 内容编写
  1.1 识别用户输入
  1.2 一次产出 script.md + outline.md
  自检 script.md / outline.md
  ↓
Checkpoint Plan：必须停，一次对齐 5 件事
  ↓
Phase 2 网页开发
  2.1 脚手架
  2.2 第 1 章主线程完整实现
  第 1 章强制验收
  2.3 第 2~N 章按模式 A/B/C 开发
  2.4 每章实现必须读 CHAPTER-CRAFT.md
  2.5 大改后 bump STORAGE_KEY
  ↓
Checkpoint Audio：必须停，问是否合成音频
  ↓
Phase 3 音频合成，可选
  ↓
Phase 4 录屏 + 后期
```

---

### 6.2 LangGraph 节点映射

| 原流程 | LangGraph 节点 | 是否 interrupt | required refs | 输出 |
|---|---|---|---:|---|
| 识别用户输入 | `wv_identify_input` | 否 | 无 | input_type |
| 保存 article / script 初稿 | `wv_prepare_source_files` | 否 | `SCRIPT-STYLE.md`, `OUTLINE-FORMAT.md` | `article.md`, `script.md`, `outline.md` |
| script 自检 | `wv_validate_script` | 否 | `SCRIPT-STYLE.md` | validation |
| script 修复 | `wv_repair_script` | 否 | `SCRIPT-STYLE.md` | revised `script.md` |
| outline 自检 | `wv_validate_outline` | 否 | `OUTLINE-FORMAT.md` | validation |
| outline 修复 | `wv_repair_outline` | 否 | `OUTLINE-FORMAT.md` | revised `outline.md` |
| Checkpoint Plan | `wv_checkpoint_plan` | 是 | themes metadata | 用户一次确认 5 件事 |
| 脚手架 | `wv_scaffold_presentation` | 否 | `THEMES.md` when custom theme | `presentation/` |
| 删除 demo | `wv_remove_example_chapter` | 否 | 无 | clean scaffold |
| 第 1 章实现 | `wv_build_chapter_1` | 否 | `CHAPTER-CRAFT.md`, theme.json, outline section, article section | chapter files |
| 第 1 章自检 | `wv_validate_chapter_1` | 否 | `CHAPTER-CRAFT.md` | validation |
| 第 1 章修复 | `wv_repair_chapter_1` | 否 | `CHAPTER-CRAFT.md` | revised chapter |
| 第 1 章验收 | `wv_checkpoint_chapter_1` | 是 | 无 | 用户反馈 / continue |
| 第 2~N 章模式分支 | `wv_select_development_mode` | 否 | 无 | A/B/C |
| 模式 A 逐章确认 | `wv_build_remaining_sequential_with_interrupts` | 每章是 | `CHAPTER-CRAFT.md` 每章必读 | chapters |
| 模式 B 顺序开发 | `wv_build_remaining_sequential_batch` | 最后是 | `CHAPTER-CRAFT.md` 每章必读 | chapters |
| 模式 C 并行开发 | `wv_build_remaining_parallel_subgraphs` | 批次后是 | `CHAPTER-CRAFT.md` 每个 subgraph 必读 | chapters |
| STORAGE_KEY 检查 | `wv_check_storage_key_bump` | 否 | 无 | possible edit |
| Checkpoint Audio | `wv_checkpoint_audio` | 是 | 无 | yes/no |
| 抽 narrations | `wv_extract_narrations` | 否 | `AUDIO.md` | `audio-segments.json` |
| 用户检查 audio-segments | `wv_checkpoint_audio_segments` | 是 | `AUDIO.md` | approve/edit |
| 合成音频 | `wv_synthesize_audio` | 否 | `AUDIO.md` | `public/audio/` |
| 音频异常报告 | `wv_report_audio_anomalies` | 否 | 无 | summary |
| 录屏路径说明 | `wv_recording_guidance` | 否 | `RECORDING.md` | final guidance |

---

### 6.3 `Checkpoint Plan` 必须完全复现

该节点必须一次性向用户对齐 5 件事：

1. `script.md` 是否要改。
2. `outline.md` 是否要改。
3. 选择哪个主题。
4. 真素材如何准备。
5. 开发模式选择 A/B/C。

不能拆成多个零散问题，也不能省略主题推荐。节点内必须先：

- 读取所有 `themes/*/theme.json`。
- 根据 `script.md` 的内容主动推荐 2~3 套主题。
- 扫描 `outline.md` 末尾素材清单。
- 构造与原 Skill 语义一致的确认 payload。
- 调用 `interrupt()`。

伪代码：

```python
def wv_checkpoint_plan(state: VideoWorkflowState):
    themes = read_all_theme_json(state.skill_root)
    recommendations = recommend_2_to_3_themes(
        script_path=state.artifact_paths["script.md"],
        themes=themes,
    )
    material_list = scan_material_list(state.artifact_paths["outline.md"])

    response = interrupt({
        "type": "checkpoint_plan",
        "files": {
            "script": state.artifact_paths["script.md"],
            "outline": state.artifact_paths["outline.md"],
        },
        "must_confirm": [
            "script",
            "outline",
            "theme",
            "materials",
            "development_mode",
        ],
        "theme_recommendations": recommendations,
        "material_list": material_list,
        "development_modes": {
            "A": "逐章确认",
            "B": "第 1 章后顺序开发",
            "C": "第 1 章后并行开发",
        }
    })

    return apply_plan_feedback(state, response)
```

---

### 6.4 第 1 章强制验收必须保留

第 1 章不能被并行化，也不能跳过人工验收。

```text
第 1 章 = 主线程 + 完整版本 + 风格锚点 + 必须停
```

LangGraph 中必须固定：

```text
wv_build_chapter_1
  → wv_validate_chapter_1
  → wv_repair_chapter_1 if failed
  → wv_checkpoint_chapter_1 interrupt
  → wv_select_development_mode
```

---

### 6.5 第 2~N 章模式 A/B/C 完全复现

#### 模式 A：默认逐章确认

```text
for chapter in 2..N:
  build chapter
  validate chapter
  repair until pass
  interrupt for chapter acceptance
```

用户不明确选择时，默认走模式 A。

#### 模式 B：第 1 章后顺序开发

```text
for chapter in 2..N:
  build chapter
  validate chapter
  repair until pass

interrupt for batch acceptance
```

#### 模式 C：第 1 章后并行开发

```text
fan out chapter subgraphs:
  each subgraph receives:
    - 当前章节 outline 段落
    - CHAPTER-CRAFT.md 路径
    - 当前主题 theme.json
    - 第 1 章代码作为代码风格参考
    - CSS 前缀要求
    - 不修改 chapters.ts
    - 完工跑 npx tsc --noEmit
fan in:
  validate all
  repair failed chapters
  interrupt for batch acceptance
```

---

### 6.6 每章实现节点必须强制读取 `CHAPTER-CRAFT.md`

每次实现单章都要重新读取，不允许只在任务开始时读一次。

实现策略：

```python
def wv_build_single_chapter(state, chapter_id):
    require_ref_loaded(
        state,
        "skills/web-video-presentation/references/CHAPTER-CRAFT.md",
        scope=f"chapter:{chapter_id}",
        reload_each_time=True,
    )
    ...
```

---

### 6.7 验收标准

| 验收项 | 必须满足 |
|---|---|
| Phase 1 | 一次产出 `script.md` + `outline.md` |
| Phase 1 自检 | `script.md` 与 `outline.md` 都必须自检并修复 |
| Checkpoint Plan | 必须 interrupt，且一次对齐 5 件事 |
| 第 1 章 | 必须主线程开发，不能并行 |
| 第 1 章 | 必须完整版本，不允许骨架版 |
| 第 1 章验收 | 必须 interrupt |
| 第 2~N 章 | 必须支持 A/B/C 三种模式 |
| 每章实现 | 必须读取 `CHAPTER-CRAFT.md` |
| 大改 | 必须检查是否 bump `STORAGE_KEY` |
| Checkpoint Audio | 必须 interrupt |
| Phase 3 | 合成前必须生成 `audio-segments.json` |
| Phase 4 | 必须根据是否有音频给出不同录屏路径 |

---

## 7. 中断节点设计

原 Skill 中的 "Checkpoint / 必须停 / 等用户确认" 全部映射为 LangGraph `interrupt()`。

### 必须中断的节点

| 节点 | 原语义 |
|---|---|
| `wv_checkpoint_plan` | script / outline / theme / materials / dev mode 一次对齐 |
| `wv_checkpoint_chapter_1` | 第 1 章强制验收 |
| `wv_checkpoint_chapter_n` | 模式 A 下每章验收 |
| `wv_checkpoint_remaining_batch` | 模式 B/C 下批量验收 |
| `wv_checkpoint_audio` | 是否合成音频 |
| `wv_checkpoint_audio_segments` | 合成前检查 audio-segments |

---

## 8. Reference 读取策略

### 8.1 原则

原 Skill 里要求"何时读"，LangGraph 必须按阶段加载，不能提前全量加载。

错误做法：

```text
启动任务时一次性读取整个 references/
```

正确做法：

```text
进入某个节点前，读取该节点原 Skill 要求的 reference 文件
```

### 8.2 required refs 表

| 阶段 | required refs |
|---|---|
| Phase 1.2 | `SCRIPT-STYLE.md`, `OUTLINE-FORMAT.md` |
| Phase 2.4 每章 | `CHAPTER-CRAFT.md` |
| 选/造/切主题 | `THEMES.md` |
| Phase 3 | `AUDIO.md` |
| Phase 4 | `RECORDING.md` |

---

## 9. Tool Adapter 设计

### 9.1 目标

不是替换原工具，而是把原工具封装成可追踪、可限制、可测试的 adapter。

| 原 Skill 工具语义 | Adapter |
|---|---|
| shell command | `ShellToolAdapter` |
| Read 局部读取 | `FileReadAdapter` |
| Grep 检索 | `GrepAdapter` |
| scaffold.sh | `WebVideoScaffoldAdapter` |
| npm scripts | `NodeScriptAdapter` |
| extract-narrations / synthesize-audio | `AudioScriptAdapter` |

### 9.2 工具调用必须记录

每次工具调用都记录：

```python
{
    "node": "wv_extract_narrations",
    "tool": "npm run extract-narrations",
    "args": {...},
    "allowed": True,
    "reason": "AUDIO.md already loaded",
    "timestamp": "..."
}
```

---

## 10. Artifact 契约

### 10.1 不改变原输出路径

工作区可以内部隔离：

```text
workspace/{thread_id}/...
```

但 Skill 对用户暴露的相对路径必须保留原约定。

web-video 的输出路径：

```text
my-video/
├── article.md
├── script.md
├── outline.md
└── presentation/
    ├── src/chapters/
    ├── audio-segments.json
    └── public/audio/
```

### 10.2 文件契约

| 文件 | 必须存在 | 说明 |
|---|---|---|
| `article.md` | 用户给原文时 | 保留原文，不删 |
| `script.md` | 是 | 平台化口播稿 |
| `outline.md` | 是 | 章节切分 + 每步内容 + 信息池 |
| `presentation/` | 是 | Vite + React + TS 项目 |
| `presentation/src/chapters/<NN>-<id>/narrations.ts` | 每章 | step 数 + 口播文本唯一真相源 |
| `audio-segments.json` | Phase 3 时 | 合成前 review |
| `public/audio/<id>/<N>.mp3` | Phase 3 后 | 合成的音频文件 |

---

## 11. 流程图（完整节点序列）

```text
START
  ↓
wv_identify_input
  ↓
wv_prepare_source_files         # 读 SCRIPT-STYLE.md + OUTLINE-FORMAT.md
  ↓
wv_validate_script
  ↓
wv_repair_script (if failed)
  ↓
wv_validate_outline
  ↓
wv_repair_outline (if failed)
  ↓
=== wv_checkpoint_plan INTERRUPT ===   # 一次对齐 5 件事
  ↓
wv_scaffold_presentation               # 读 THEMES.md (custom theme)
  ↓
wv_remove_example_chapter
  ↓
wv_build_chapter_1                     # 读 CHAPTER-CRAFT.md + theme.json + outline
  ↓
wv_validate_chapter_1
  ↓
wv_repair_chapter_1 (if failed)
  ↓
=== wv_checkpoint_chapter_1 INTERRUPT ===
  ↓
wv_select_development_mode             # → A / B / C
  ↓
┌─ A: [for each ch 2..N]
│     wv_build_chapter_N
│     wv_validate_chapter_N
│     wv_repair_chapter_N (if failed)
│   === wv_checkpoint_chapter_N INTERRUPT ===
│
├─ B: [for each ch 2..N, sequential]
│     wv_build_chapter_N
│     wv_validate_chapter_N
│     wv_repair_chapter_N (if failed)
│   === wv_checkpoint_remaining_batch INTERRUPT ===
│
└─ C: [fan-out subgraphs for ch 2..N]
       each: build → validate → repair
     [fan-in]
   === wv_checkpoint_remaining_batch INTERRUPT ===
  ↓
wv_check_storage_key_bump
  ↓
=== wv_checkpoint_audio INTERRUPT ===   # 是否合成音频
  ↓ (yes)                  ↓ (no)
wv_extract_narrations      ↓
  ↓                         ↓
=== wv_checkpoint_audio_segments ===   ↓
  ↓                         ↓
wv_synthesize_audio         ↓
  ↓                         ↓
wv_report_audio_anomalies   ↓
  ↓                         ↓
wv_recording_guidance  ←───┘
  ↓
END
```

---

## 12. API 层设计

### 12.1 REST API 端点

| 方法 | 路径 | 用途 | 请求体 | 响应 |
|---|---|---|---|---|
| `POST` | `/api/workflow/start` | 启动新工作流 | `{user_request, language?, input_type?}` | `{thread_id, state}` |
| `POST` | `/api/workflow/{thread_id}/resume` | 恢复中断的工作流 | `{confirmations}` | `{state}` |
| `GET` | `/api/workflow/{thread_id}` | 查询当前状态 | — | `{thread_id, current_node, interrupt_data, ...}` |
| `GET` | `/api/workflow/{thread_id}/events` | SSE 事件流 | — | `text/event-stream` |
| `POST` | `/api/workflow/{thread_id}/cancel` | 取消运行 | — | `{status: "cancelled"}` |
| `GET` | `/api/workflow/{thread_id}/artifacts` | 列出产出的文件列表 | — | `{files: [{path, size, modified}]}` |
| `GET` | `/api/workflow/{thread_id}/artifact/{path:path}` | 读取某个产出文件内容 | — | 文件原始内容 |
| `GET` | `/api/themes` | 列出所有可用主题 | — | `{themes: [{id, nameZh, descriptionZh, bestFor}]}` |

### 12.2 `POST /api/workflow/start`

启动新工作流。根据 `input_type` 决定走哪个入口：

- `"article"`：用户给了原文 → 全流程（Phase 1 写稿 + outline）
- `"script"`：用户给了口播稿 → 简化流程（只写 outline）
- `"none"`：用户什么都没有 → 反问，不启动图

```python
@router.post("/workflow/start")
async def start_workflow(req: StartRequest):
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = VideoWorkflowState(
        thread_id=thread_id,
        run_id=str(uuid4()),
        user_request=req.user_request,
        language=req.language or "zh-CN",
        input_type=req.input_type,
        current_phase="phase1",
        current_node="wv_identify_input",
        completed_nodes=[],
        pending_interrupt=None,
        skill_root="skills/web-video-presentation",
        required_refs=[],
        loaded_refs=[],
        workspace_root=f"workspace/{thread_id}",
        artifact_paths={},
        created_files=[],
        modified_files=[],
        user_confirmations={},
        validation_results=[],
        repair_history=[],
        errors=[],
        allowed_tools=[],
        denied_tools=[],
        tool_calls=[],
        final_summary=None,
    )

    # 首次 invoke，运行直到第一个 interrupt 或 END
    result = await graph.ainvoke(initial_state, config)

    return {
        "thread_id": thread_id,
        "state": serialize_state(result),
    }
```

### 12.3 `POST /api/workflow/{thread_id}/resume`

恢复中断的工作流。用户确认信息通过 `confirmations` 传入，LangGraph 通过 `Command(resume=...)` 恢复。

```python
@router.post("/workflow/{thread_id}/resume")
async def resume_workflow(thread_id: str, req: ResumeRequest):
    config = {"configurable": {"thread_id": thread_id}}

    # Command(resume=value) 会从 interrupt() 返回 value
    result = await graph.ainvoke(
        Command(resume=req.confirmations),
        config,
    )

    return {
        "thread_id": thread_id,
        "state": serialize_state(result),
    }
```

### 12.4 SSE 事件流

前端通过 SSE 订阅工作流状态变更：

```text
GET /api/workflow/{thread_id}/events

data: {"type": "node_enter", "node": "wv_validate_script", "ts": "..."}
data: {"type": "node_exit", "node": "wv_validate_script", "ts": "..."}
data: {"type": "interrupt", "checkpoint_type": "checkpoint_plan", "payload": {...}}
data: {"type": "completed", "summary": "..."}
```

### 12.5 错误处理

| 错误 | HTTP 状态码 | body |
|---|---|---|
| thread_id 不存在 | 404 | `{error: "workflow_not_found", message: "..."}` |
| 工作流未被中断 | 400 | `{error: "not_interrupted", message: "..."}` |
| 节点执行异常 | 500 | `{error: "node_execution_error", node: "...", detail: "..."}` |
| Policy 违规 | 403 | `{error: "policy_violation", message: "...", missing_refs: [...]}` |

---

## 13. 前端设计

### 13.1 技术选型

- React 18 + TypeScript + Vite（与 presentation 脚手架一致的技术栈）
- 原生 CSS（不引入 UI 框架，保持轻量）
- fetch + SSE 与后端通信

### 13.2 页面路由

| 路由 | 组件 | 用途 |
|---|---|---|
| `/` | `HomePage` | 首页，选择创建新项目或恢复已有项目 |
| `/new` | `NewProjectPage` | 输入文章或口播稿 |
| `/workflow/:id` | `WorkflowPage` | 工作流主页面，根据当前节点动态渲染子组件 |
| `/workflow/:id/checkpoint-plan` | `CheckpointPlan` | 一次确认 5 件事（口播稿/outline/主题/素材/模式） |
| `/workflow/:id/chapter/:n` | `ChapterReview` | 章节验收（含 checklist） |
| `/workflow/:id/checkpoint-audio` | `CheckpointAudio` | 是否合成音频 |
| `/workflow/:id/progress` | `ProgressPanel` | 查看整体进度、节点执行历史、产出文件 |

### 13.3 核心组件树

```text
App
├── Header                     # logo + thread_id + 状态标签
└── Routes
    ├── HomePage
    ├── NewProjectPage
    │   └── InputForm           # textarea + input_type 选择
    └── WorkflowPage
        ├── ProgressSidebar     # 左侧进度条，显示已完成/当前/待办节点
        └── MainPanel
            ├── PhaseIndicator  # 当前阶段名 + 描述
            ├── DynamicContent  # 根据 current_node 渲染不同内容
            │   ├── CheckpointPlanView      # 主题选择卡片 / outline 预览 / 模式选择
            │   ├── ChapterReviewView       # 第 N 章验收 + checklist
            │   ├── CheckpointAudioView     # yes/no 选择
            │   ├── TextPreview             # script.md / outline.md 预览
            │   └── LoadingState            # 节点执行中的等待状态
            ├── ArtifactPanel   # 已产出文件列表 + 预览链接
            └── NodeTimeline    # 底部节点执行时间线
```

### 13.4 主题选择卡片（Checkpoint Plan 核心 UI）

每个主题以卡片形式展示，包含：

- 主题名称 (nameZh) + 英文名
- 简短描述 (descriptionZh)
- 预览色板 (preview.shell / surface / text / accent)
- bestFor 标签（适合什么类型内容）
- 选中后高亮，底部确认按钮

```text
┌──────────────────────────────────────────┐
│ 请选择主题                                  │
│                                            │
│ ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│ │暗色印刷  │  │论文印刷  │  │暖色演讲  │   │
│ │Midnight  │  │Paper     │  │Warm     │   │
│ │Press     │  │Press     │  │Keynote  │   │
│ │          │  │          │  │         │   │
│ │■ #0d0b09 │  │■ #f5f0e5 │  │■ #faf8f5│   │
│ │■ #1a1714 │  │■ #ffffff │  │■ #ffffff│   │
│ │■ #ff4a2b │  │■ #e8563a │  │■ #1a7f6e│   │
│ │          │  │          │  │         │   │
│ │开发者教程 │  │产品发布  │  │产品演讲  │   │
│ │AI/工具评测│  │新闻式内容 │  │SaaS演示  │   │
│ └─────────┘  └─────────┘  └─────────┘   │
│                                            │
│ [确认选择]                                  │
└──────────────────────────────────────────┘
```

### 13.5 状态同步

前端通过两种方式同步后端状态：

1. **初始加载**：`GET /api/workflow/{id}` 获取完整状态
2. **实时更新**：`GET /api/workflow/{id}/events` SSE 订阅事件流

当用户提交确认后：

```
前端 POST /api/workflow/{id}/resume
  → 后端调用 Command(resume=...)
  → LangGraph 继续执行
  → 遇到下一个 interrupt 或执行完成
  → SSE 推送 state_change 事件
  → 前端重新渲染
```

---

## 14. 完整的项目结构

```text
ezto-agent/
├── app/
│   ├── api/                         # FastAPI 后端
│   │   ├── __init__.py
│   │   ├── server.py                # FastAPI app 入口
│   │   ├── routes.py                # REST 路由定义
│   │   ├── models.py                # Pydantic 请求/响应模型
│   │   └── workflow_manager.py      # LangGraph invoke/resume 管理
│   ├── graph/
│   │   └── web_video.py             # 完全复现 web-video-presentation 的 LangGraph
│   ├── runtime/
│   │   ├── state.py                 # 统一状态定义
│   │   ├── interrupts.py            # 原 checkpoint → LangGraph interrupt
│   │   ├── artifact_manager.py      # 原输出路径契约
│   │   ├── ref_loader.py            # references 强制读取记录
│   │   ├── tool_adapters.py         # Shell / Read / Grep / scaffold 等工具封装
│   │   └── guards.py                # 禁止行为拦截
│   └── observability/
│       ├── trace_logger.py
│       └── audit_logger.py
│
├── frontend/                        # React + Vite 前端
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                  # 路由配置
│   │   ├── api/
│   │   │   └── client.ts           # 后端 API 调用封装
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── NewProjectPage.tsx
│   │   │   └── WorkflowPage.tsx
│   │   ├── components/
│   │   │   ├── CheckpointPlanView.tsx
│   │   │   ├── ChapterReviewView.tsx
│   │   │   ├── CheckpointAudioView.tsx
│   │   │   ├── PhaseIndicator.tsx
│   │   │   ├── ArtifactPanel.tsx
│   │   │   ├── NodeTimeline.tsx
│   │   │   └── LoadingState.tsx
│   │   └── styles/
│   │       ├── base.css
│   │       └── pages.css
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── skills/
│   └── web-video-presentation/
│       ├── SKILL.md
│       ├── references/
│       ├── scripts/
│       ├── templates/
│       └── themes/
│
├── workspace/
│   └── {thread_id}/
│
├── tests/
│   ├── flow_parity/
│   ├── golden_traces/
│   └── fixtures/
│
└── pyproject.toml
```

---

## 15. Flow Parity 测试方案

### 12.1 Golden Trace

最小输入的期望 trace：

```text
wv_identify_input
wv_prepare_source_files
wv_validate_script
wv_validate_outline
wv_checkpoint_plan INTERRUPT
wv_scaffold_presentation
wv_remove_example_chapter
wv_build_chapter_1
wv_validate_chapter_1
wv_checkpoint_chapter_1 INTERRUPT
wv_select_development_mode
wv_build_chapter_2
wv_validate_chapter_2
wv_checkpoint_chapter_2 INTERRUPT
wv_check_storage_key_bump
wv_checkpoint_audio INTERRUPT
wv_recording_guidance
```

### 12.2 Reference Policy Test

测试目标：

```text
任何节点使用某类文件/任务前，required refs 必须已加载。
```

例子：

```python
def test_chapter_requires_craft_ref():
    state = make_empty_state()
    state.loaded_refs = []
    with pytest.raises(PolicyViolation):
        wv_build_single_chapter(state, chapter_id=2)
```

### 12.3 Interrupt Parity Test

测试目标：

- 原 Skill 的所有硬节点必须有 interrupt。
- interrupt payload 必须包含原 Skill 要用户确认的信息。
- resume 后必须进入原流程的下一节点。

### 12.4 Artifact Contract Test

测试目标：

- 必须产出 `script.md` 和 `outline.md`。
- 第 1 章后必须有 chapter 文件。
- 必须产出 `presentation/` 项目。
- Phase 3 后必须有 `audio-segments.json`。

---

## 13. 实施计划

### Phase 0：流程固化与测试样例

产出：

- `docs/skill-flow-parity.md` — 流程映射文档
- 流程图（完整节点序列）
- golden trace
- required refs 表
- 禁止行为表

完成标准：

- 人工确认流程映射无遗漏
- 每个原 checkpoint 都有对应 LangGraph interrupt
- 每个 references 强制读取点都有 policy guard

---

### Phase 1：基础运行时

产出：

```text
runtime/state.py
runtime/interrupts.py
runtime/artifact_manager.py
runtime/ref_loader.py
runtime/guards.py
runtime/tool_adapters.py
```

完成标准：

- 能定位 skill root
- 能创建 thread workspace
- 能记录 loaded refs
- 能记录 tool calls
- 能抛出 policy violation

---

### Phase 2：实现后端 API

产出：

```text
app/api/server.py
app/api/routes.py
app/api/models.py
app/api/workflow_manager.py
```

完成标准：

- `POST /api/workflow/start` 能启动 LangGraph 并返回 thread_id
- `POST /api/workflow/{id}/resume` 能恢复中断
- `GET /api/workflow/{id}` 返回当前状态
- SSE 事件流推送节点变更
- 主题列表接口可读 `themes/*/theme.json`
- artifact 文件列表和内容可查询

---

### Phase 3：实现前端

产出：

```text
frontend/  (React + Vite + TS)
```

页面覆盖：首页 / 新项目 / 工作流主页面 / Checkpoint Plan / 章节验收 / Audio 选择

完成标准：

- 输入文章后能看到完整工作流推进
- Checkpoint Plan 页面展示 5 件事一次对齐
- 主题选择以卡片形式展示色板和推荐
- 章节验收展示 checklist
- SSE 实时更新执行进度
- 能查看已产出文件

---

### Phase 4：实现 web-video 子图

产出：

```text
graph/web_video.py
```

包含所有 20+ 个节点、条件边、interrupt、subgraph fan-out。

完成标准：

- Phase 1 → 6 完整流程可运行
- 所有 checkpoint 触发 interrupt
- 三种开发模式 A/B/C 按条件分支
- 模式 C 能 fan-out 并行开发章节

---

### Phase 5：Flow Parity 测试

产出：

```text
tests/flow_parity/test_web_video_flow.py
```

完成标准：

- golden trace 通过
- required refs 测试通过
- artifact contract 测试通过
- interrupt parity 测试通过
- API 端点集成测试通过
- 前端关键交互流程测试通过

---

### Phase 6：承载层

在不改变流程的前提下加入：

- thread / workspace 隔离
- audit log
- LangSmith tracing
- cost tracking
- retry / resume

注意：这些是承载层，不得影响节点顺序。

---

## 14. 最终验收标准

### 14.1 总体验收

| 类别 | 标准 |
|---|---|
| 流程复现 | 节点顺序与原 `SKILL.md` 一致 |
| 硬节点 | 原 checkpoint 全部变成 interrupt |
| references | 原 required refs 全部强制读取 |
| 禁止行为 | 原禁止行为全部由 Guard 拦截 |
| 输出契约 | 原输出目录和文件命名不变 |
| 模式分支 | 原 A/B/C 开发模式完整保留 |
| 用户体验 | 用户看到的流程与原 Skill 一致 |
| 企业能力 | 可恢复、可追踪、可审计，但不改变流程 |

### 14.2 一票否决项

出现以下任一情况，判定为"不符合完全复现"：

- 没有 Checkpoint Plan
- 第 1 章没有强制验收
- 第 2~N 章不支持 A/B/C 三种模式
- 每章实现没有读 `CHAPTER-CRAFT.md`
- 原输出目录被替换成另一套对外路径

---

## 15. 建议的最小代码骨架

```python
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

class VideoWorkflowState(TypedDict):
    user_request: str
    current_phase: str
    loaded_refs: list[str]
    artifact_paths: dict
    user_confirmations: dict
    errors: list[dict]

builder = StateGraph(VideoWorkflowState)

# Phase 1 nodes
builder.add_node("wv_identify_input", wv_identify_input)
builder.add_node("wv_prepare_source_files", wv_prepare_source_files)
builder.add_node("wv_validate_script", wv_validate_script)
builder.add_node("wv_repair_script", wv_repair_script)
builder.add_node("wv_validate_outline", wv_validate_outline)
builder.add_node("wv_repair_outline", wv_repair_outline)
builder.add_node("wv_checkpoint_plan", wv_checkpoint_plan)
# ... remaining nodes

builder.add_edge(START, "wv_identify_input")
builder.add_conditional_edges("wv_validate_script", route_script_validation)
# ... remaining edges

graph = builder.compile(checkpointer=durable_checkpointer)
```

---

## 16. 结论

本次重构应定义为：

```text
基于 LangGraph 对 web-video-presentation 的原 Skill 流程进行状态机化复现。
```

而不是：

```text
基于 LangGraph 重新设计一个更通用的多 Agent 产品。
```

正确落地顺序是：

```text
1. 逐节点复现原流程
2. 加入 interrupt 保留硬 checkpoint
3. 加入 required refs guard 保留强制读取
4. 加入 artifact contract 保留输出约定
5. 加入 parity tests 保证行为一致
6. 最后再加承载层能力
```

最终系统的成功标准不是"看起来更高级"，而是：

```text
同一个用户请求，在原 Skill 和 LangGraph 版本中，
应经历相同的阶段、相同的停顿点、相同的必读文件、
相同的工具语义、相同的输出契约。
```
