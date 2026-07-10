# ezto_video

文章/口播稿 → 点击驱动的 16:9 网页视频演示 — 基于 LangGraph 的自动化流程引擎。

## 项目结构

```
ezto_video/
├── ezto-agent/                       # 主要工作区
│   ├── src/
│   │   ├── backend/                  # FastAPI 后端服务
│   │   │   ├── api/                  # REST 路由、模型、服务器入口
│   │   │   │   ├── server.py         # uvicorn 入口 (uvicorn backend.api.server:app)
│   │   │   │   ├── routes.py         # REST 端点 + SSE 事件流
│   │   │   │   ├── models.py         # Pydantic 请求/响应模型
│   │   │   │   └── deps.py           # 依赖注入
│   │   │   ├── core/                 # 配置、LLM 客户端、日志、异常
│   │   │   │   ├── settings.py       # pydantic-settings 环境配置
│   │   │   │   ├── llm.py            # DeepSeek 客户端 (OpenAI 兼容)
│   │   │   │   ├── logger.py         # 控制台 + 文件 + LLM 交互日志
│   │   │   │   └── exceptions.py     # 自定义异常
│   │   │   ├── services/             # 业务服务层
│   │   │   │   ├── workflow_service.py   # LangGraph 工作流编排
│   │   │   │   ├── project_service.py    # 项目管理
│   │   │   │   ├── artifact_service.py   # 产出文件管理
│   │   │   │   ├── event_service.py      # SSE 事件推送
│   │   │   │   └── workspace_service.py  # 工作区管理
│   │   │   └── main.py               # CLI 启动入口
│   │   │
│   │   ├── harness/                  # LangGraph 工作流引擎
│   │   │   ├── core/
│   │   │   │   ├── state.py          # VideoWorkflowState (TypedDict)
│   │   │   │   ├── config.py         # 运行时配置
│   │   │   │   ├── events.py         # 事件定义
│   │   │   │   └── runtime.py        # 运行时上下文
│   │   │   ├── agent/
│   │   │   │   ├── loop.py           # LLM 调用循环
│   │   │   │   ├── prompts.py        # 系统提示词管理
│   │   │   │   └── tools.py          # agent 工具定义
│   │   │   ├── workflow/
│   │   │   │   ├── builder.py        # 22 节点 StateGraph 构建
│   │   │   │   ├── nodes/
│   │   │   │   │   ├── content.py    # 内容编写阶段节点 (wv_identify_input → checkpoint_plan)
│   │   │   │   │   ├── web.py        # 网页开发阶段节点 (scaffold → build chapters)
│   │   │   │   │   ├── audio.py      # 音频合成阶段节点
│   │   │   │   │   └── recording.py  # 录屏指引节点
│   │   │   │   ├── artifacts.py      # think/act 工具、修复计数、输出验证
│   │   │   │   ├── guards.py         # 策略违规守卫
│   │   │   │   └── interruptions.py  # Checkpoint → LangGraph interrupt 映射
│   │   │   └── services/
│   │   │       └── tools/            # 工具适配器
│   │   │           ├── shell.py      # Shell 命令执行
│   │   │           ├── scaffold.py   # 项目脚手架
│   │   │           ├── npm.py        # npm 命令
│   │   │           ├── typescript.py # tsc 类型检查
│   │   │           └── file_ops.py   # 文件操作
│   │   │
│   │   └── frontend/                 # React + Vite + TS 工作流 UI
│   │       └── src/
│   │           ├── pages/            # HomePage, NewProjectPage, WorkflowPage
│   │           ├── components/       # CheckpointPlanView, ChapterReviewView, ExecutionStream, …
│   │           ├── api/client.ts     # 后端 API + SSE 工具函数
│   │           └── styles/base.css   # 全局样式
│   │
│   ├── assets/                       # 运行时资源（原位于 app/ 和 skills/ 下）
│   │   ├── templates/                # Vite + React + TS 脚手架模板
│   │   │   ├── src/                  # 模板源码（Stage, Stepper, chapters, hooks）
│   │   │   ├── components/           # AutoStartGate, AutoToggle, ProgressBar 等
│   │   │   ├── hooks/                # useAudioPlayer, useAutoMode, useStageScale, useStepper
│   │   │   ├── registry/             # 章节注册表
│   │   │   └── scripts/             # scaffold.sh, extract-narrations.ts
│   │   ├── themes/                   # 23 套主题 (每个目录 theme.json + tokens.css)
│   │   ├── references/               # 阶段参考文档
│   │   │   ├── CHAPTER-CRAFT.md      # 章节构建规则
│   │   │   ├── SCRIPT-STYLE.md       # 脚本风格指南
│   │   │   ├── OUTLINE-FORMAT.md     # 大纲格式规范
│   │   │   ├── THEMES.md             # 主题系统文档
│   │   │   ├── AUDIO.md              # 音频合成指南
│   │   │   ├── RECORDING.md          # 录屏指引
│   │   │   └── EXAMPLES/             # hook-chapter, list-reveal, case-tech-review
│   │   └── examples/                 # 参考案例
│   │
│   ├── runtime/                      # 运行时数据目录
│   │   ├── logs/                     # 应用日志 (ezto-agent.log, llm.log)
│   │   ├── cache/                    # 网站构建的缓存（用于网站构建的可复用的包，省的每次都要重新下载一遍）
│   │   └── workspace/                # 项目工作区
│   │
│   ├── tests/
│   │   ├── backend/                  # 后端单元测试
│   │   ├── harness/                  # 工作流引擎测试
│   │   └── flow_parity/              # Golden trace + 流程对等性测试
│   │
│   ├── scripts/                      # 部署与工具脚本
│   │   ├── setup_wsl.sh              # WSL conda 一键配置
│   │   └── start_backend.sh          # 后端启动脚本
│   │
│   └── pyproject.toml                # Python 项目依赖（langgraph, fastapi, pydantic）
│
├── skills/web-video-presentation/    # 原 Claude Code Skill（方法论真相源）
│   ├── SKILL.md                      # 完整流程规范（LangGraph 需保持对等）
│   ├── templates/                    # 脚手架模板（assets/templates 的源）
│   ├── themes/                       # 23 套主题（assets/themes 的源）
│   └── references/                   # 规则文档（assets/references 的源）
│
├── docs/                             # 架构与设计文档
│   ├── graph.mmd / graph.png         # LangGraph 流程图
│   ├── graph-cn.mmd / graph-cn.png   # 中文版流程图
│   ├── checkpoint_plan_flow.md       # Checkpoint Plan 交互流程
│   ├── web_video_graph_guide.md      # 图结构详细指南
│   ├── code-mapping.md               # 代码映射表
│   ├── frontend-testing.md           # 前端测试策略
│   ├── skill-flow-parity.md          # Skill ↔ LangGraph 对等性分析
│   └── notes.md                      # 开发笔记
│
├── CLAUDE.md                         # Claude Code 项目指令
└── ezto_video_langgraph_flow_parity_plan.md  # 流程对等性迁移计划
```

## 架构概览

```
                             ┌──────────────────┐
                             │    FastAPI 后端    │
                             │  src/backend/api/  │
                             │  :8001             │
                             └────────┬─────────┘
                                      │ SSE + REST
                             ┌────────▼─────────┐
                             │  WorkflowManager  │
                             │ workflow_service  │
                             └────────┬─────────┘
                                      │ invoke
                             ┌────────▼─────────┐
                             │  LangGraph 引擎   │
                             │  src/harness/     │
                             │  22 节点状态机    │
                             └──────────────────┘
```

### LangGraph 工作流（4 阶段，22 节点）

| 阶段 | 节点 | 说明 |
|------|------|------|
| **Phase 1: 内容编写** | `wv_identify_input` → `wv_prepare_source_files` → `wv_validate_script` ↻ (repair) → `wv_validate_outline` ↻ (repair) → **`wv_checkpoint_plan`** | 识别输入 → 生成 script.md + outline.md → 自检修复 → 用户确认 |
| **Phase 2: 网页开发** | `wv_scaffold_presentation` → `wv_remove_example_chapter` → `wv_build_chapter_1` ↻ → **`wv_checkpoint_chapter_1`** → `wv_build_chapter_n` ↻ → **`wv_checkpoint`** per mode | scaffold → 第 1 章（强制验收）→ 第 2~N 章（A/B/C 模式） |
| **Phase 3: 音频合成** | **`wv_checkpoint_audio`** → `wv_extract_narrations` → **`wv_checkpoint_audio_segments`** → `wv_synthesize_audio` | 可选 TTS（MiniMax / OpenAI） |
| **Phase 4: 录屏** | `wv_recording_guidance` → END | 录屏指引 |

关键设计点：
- **6 个 Checkpoint 中断**：plan, chapter_1, chapter_n, batch, audio, segments
- **validate-repair 循环**：script.md / outline.md / 每章最多 3 次重试
- **3 种开发模式**：A = 顺序 + 逐章中断，B = 顺序 + 批量，C = 并行子图
- **参考文档按阶段加载**：由 guards.py 强制执行，非一次性全加载
- **产出合约**：文件必须创建在预期路径（由 artifact_manager 保障）

## 后端部署（WSL）

```bash
wsl

# 1. 确保 Miniconda 已安装，创建环境
conda create -n ezto python=3.12 -y

# 2. 激活环境并安装依赖
conda activate ezto
cd ezto-agent
pip install -e .

# 3. 配置环境变量（复制并填写）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 等

# 4. 启动服务
cd src
uvicorn backend.api.server:app --reload --port 8001

# 5. 验证
curl http://localhost:8001/health
# 返回 {"status": "ok"}
```

也可一键配置：`bash ezto-agent/scripts/setup_wsl.sh`

## 前端启动

```bash
cd ezto-agent/src/frontend
npm install
# Vite dev server，默认 :5173
npm run dev       
# 生产构建  
npm run build       
```

## 在 scaffold 项目内

```bash
cd presentation
npm run dev                  # 启动演示预览（默认 :5202）
npx tsc --noEmit             # TypeScript 类型检查
npm run extract-narrations   # 扫描章节 → audio-segments.json
npm run synthesize-audio     # TTS 合成
```

## API 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/workflow/start` | 启动新工作流 |
| POST | `/api/workflow/{id}/resume` | 恢复中断的工作流 |
| GET  | `/api/workflow/{id}` | 查询当前状态 |
| GET  | `/api/workflow/{id}/events` | SSE 事件流（实时推送） |
| GET  | `/api/workflow/{id}/artifacts` | 列出产出文件 |
| GET  | `/api/workflow/{id}/artifact/{path}` | 读取产出文件内容 |
| GET  | `/api/themes` | 列出 23 套主题 |
| GET  | `/health` | 健康检查 |

## 启动一个完整工作流

```bash
# 1. 确保后端运行（:8001）

# 2. 提交文章/口播稿
curl -X POST http://localhost:8001/api/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"user_request": "你的文章内容或口播稿...", "language": "zh-CN"}'

# 3. 查询状态（看到 pending_interrupt 后继续）
curl http://localhost:8001/api/workflow/<thread_id>

# 4. 恢复中断（确认 Checkpoint Plan）
curl -X POST http://localhost:8001/api/workflow/<thread_id>/resume \
  -H "Content-Type: application/json" \
  -d '{"confirmations": {"checkpoint_plan": {"selected_theme": "midnight-press", "development_mode": "A", ...}}}'
```

## 核心模型（网页演示规范）

- **固定 16:9 舞台**：1920×1080 内容，`transform: scale()` 适配视口
- **全局 `(chapter, step)` 光标**：单一 useState 步进器，章节是 `step` 的纯函数
- **`narrations.ts` 是真相源**：数组长度 === 步骤总数
- **3 种播放模式**：`manual`（点击）、`audio`（播放+点击）、`auto`（播放+自动推进）
- **主题令牌系统**：23 套主题通过 CSS 自定义属性，无硬编码颜色/字体
- **一键一步**：每个 step 独占全屏（`if (step === N) return <Scene />`）
- **隐藏式 Chrome**：进度条仅 hover 显示，无页眉/页脚/页码
- **内容驱动动画优先于入场动画**
- **多点揭示必须 1 步 1 项**
- **动画时长 ≤ 旁白时长**

## 开发命令速查

```bash
# 后端
cd ezto-agent && uvicorn backend.api.server:app --reload --port 8001

# 前端
cd ezto-agent/src/frontend && npm run dev

# 测试
cd ezto-agent && pytest

# 类型检查（项目模板内）
cd presentation && npx tsc --noEmit
```

## 完整文档

- `skills/web-video-presentation/SKILL.md` — 完整流程规范（LangGraph 需保持对等）
- `docs/graph.mmd` — LangGraph 流程图
- `docs/web_video_graph_guide.md` — 图结构详细指南
- `docs/code-mapping.md` — 代码映射表
- `docs/checkpoint_plan_flow.md` — Checkpoint Plan 交互流程
