<div align="center">

<pre style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;letter-spacing:0.35em;color:#737373;margin:0 0 12px 0;">E Z T O &nbsp; V I D E O</pre>

# 文章到网页视频

### 面向 16:9 点击驱动演示的 Agent 工作流

<br/>

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-171717?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/LangGraph-22%20nodes-171717?style=flat-square" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-171717?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React%20%2B%20Vite-Frontend-171717?style=flat-square&logo=react&logoColor=61DAFB" alt="React"/>
  <img src="https://img.shields.io/badge/Themes-23-D4AF37?style=flat-square&labelColor=171717" alt="Themes"/>
</p>

<br/>

<p style="max-width:640px;margin:0 auto;font-size:15px;line-height:1.75;color:#404040;">
文稿 / 口播稿 → 校验大纲 → 主题化 React 演示 → 可选 TTS → 可录制的网页视频
</p>

<br/>

<p>
  <a href="#摘要">摘要</a> ·
  <a href="#核心贡献">贡献</a> ·
  <a href="#界面展示">界面</a> ·
  <a href="#方法">方法</a> ·
  <a href="#快速开始">开始</a> ·
  <a href="#文档">文档</a>
</p>

</div>

<br/>

<p align="center">
  <img src="docs/figures/teaser.svg" alt="端到端流水线总览" width="92%"/>
</p>

<p align="center">
  <sub>
    <b>图 1</b> · 端到端：源文本进入，交互式 16:9 网页演示输出<br/>
    替换 <code>docs/figures/teaser.svg</code> 为总览拼图
  </sub>
</p>

---

## 摘要

长文转成精致讲解视频，至今仍大量依赖人工：改写口播、排版幻灯、设计揭示动画、对齐旁白、再录屏。**ezto_video** 把这条链路做成**确定性 Agent 工作流**。

方法论最初沉淀在 Claude Code Skill（`skills/web-video-presentation/`）里；本仓库将其提升为 **22 节点 LangGraph**：带检查点中断、校验–修复循环，以及 FastAPI + React 控制台——让 Agent 产出的是可点击、主题令牌化、可录制的演示，而不是一次性幻灯堆砌。

---

## 核心贡献

<table>
  <tr>
    <td width="20%" valign="top"><b>Skill → Graph</b></td>
    <td>方法论以类型化状态机执行，而非自由闲聊式循环</td>
  </tr>
  <tr>
    <td valign="top"><b>人在回路</b></td>
    <td>6 处硬检查点：计划 · 第 1 章 · 第 N 章 / 批量 · 音频 · 片段</td>
  </tr>
  <tr>
    <td valign="top"><b>自修复</b></td>
    <td>script / outline / 各章最多 3 轮 validate–repair</td>
  </tr>
  <tr>
    <td valign="top"><b>演示工艺</b></td>
    <td>固定 16:9 舞台 · <code>(chapter, step)</code> 光标 · narrations 为真相源 · 23 套主题</td>
  </tr>
  <tr>
    <td valign="top"><b>开发模式</b></td>
    <td>A 顺序逐章 · B 顺序批量 · C 并行子图</td>
  </tr>
</table>

---

## 界面展示

> 下方为占位图。将截图覆盖同名文件即可（PNG / WebP 亦可，记得改扩展名）。建议宽幅或 16:9。

### 01 · 入口

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="docs/figures/ui-home.svg" alt="入口首页" width="100%"/>
      <br/><br/>
      <sub><b>首页</b><br/>项目列表与入口<br/><code>ui-home.*</code></sub>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="docs/figures/ui-new-project.svg" alt="新建项目" width="100%"/>
      <br/><br/>
      <sub><b>新建项目</b><br/>粘贴文章 / 口播稿<br/><code>ui-new-project.*</code></sub>
    </td>
  </tr>
</table>

### 02 · 过程

<table>
  <tr>
    <td width="33%" align="center" valign="top">
      <img src="docs/figures/ui-checkpoint-plan.svg" alt="计划检查点" width="100%"/>
      <br/><br/>
      <sub><b>检查点 · 计划</b><br/>主题与模式确认<br/><code>ui-checkpoint-plan.*</code></sub>
    </td>
    <td width="33%" align="center" valign="top">
      <img src="docs/figures/ui-chapter-build.svg" alt="章节构建" width="100%"/>
      <br/><br/>
      <sub><b>构建中</b><br/>SSE 执行流<br/><code>ui-chapter-build.*</code></sub>
    </td>
    <td width="33%" align="center" valign="top">
      <img src="docs/figures/ui-chapter-review.svg" alt="章节验收" width="100%"/>
      <br/><br/>
      <sub><b>检查点 · 章节</b><br/>预览与批准<br/><code>ui-chapter-review.*</code></sub>
    </td>
  </tr>
</table>

<p align="center">
  <img src="docs/figures/ui-audio.svg" alt="音频合成界面" width="72%"/>
</p>
<p align="center">
  <sub><b>音频（可选）</b> · 片段审阅与 TTS · <code>ui-audio.*</code></sub>
</p>

### 03 · 成果

<table>
  <tr>
    <td width="33%" align="center" valign="top">
      <img src="docs/figures/result-presentation.svg" alt="最终演示舞台" width="100%"/>
      <br/><br/>
      <sub><b>舞台</b><br/>1920×1080 缩放视口<br/><code>result-presentation.*</code></sub>
    </td>
    <td width="33%" align="center" valign="top">
      <img src="docs/figures/result-steps.svg" alt="步进揭示" width="100%"/>
      <br/><br/>
      <sub><b>步进</b><br/>一键一意<br/><code>result-steps.*</code></sub>
    </td>
    <td width="33%" align="center" valign="top">
      <img src="docs/figures/result-themes.svg" alt="主题变体" width="100%"/>
      <br/><br/>
      <sub><b>主题</b><br/>令牌驱动皮肤<br/><code>result-themes.*</code></sub>
    </td>
  </tr>
</table>

<p align="center">
  <sub>
    <b>图 2</b> · 界面画廊：入口 → 检查点 → 交付物<br/>
    建议截取：HomePage · NewProjectPage · CheckpointPlanView · ExecutionStream · ChapterReviewView · 成片预览
  </sub>
</p>

---

## 方法

### 系统架构

<p align="center">
  <img src="docs/figures/architecture.svg" alt="系统架构" width="88%"/>
</p>

<p align="center">
  <sub>
    <b>图 3</b> · React 控制台 ↔ FastAPI / SSE ↔ LangGraph 引擎 ↔ 脚手架演示工程<br/>
    替换 <code>docs/figures/architecture.svg</code>；也可参考已有 <a href="docs/graph.png">graph.png</a> / <a href="docs/graph-cn.png">graph-cn.png</a>
  </sub>
</p>

```text
  ┌─────────────────┐     REST + SSE      ┌──────────────────┐
  │  React 前端      │ ◄─────────────────► │  FastAPI (:8001) │
  │  工作流控制台     │                     │  workflow service │
  └─────────────────┘                     └────────┬─────────┘
                                                   │ invoke / resume
                                          ┌────────▼─────────┐
                                          │  LangGraph (22)  │
                                          │  harness/        │
                                          └────────┬─────────┘
                                                   │ artifacts
                                          ┌────────▼─────────┐
                                          │  presentation/   │
                                          │  Vite · React · TS│
                                          └──────────────────┘
```

### 流水线 · 4 阶段 · 22 节点

```text
阶段 1  内容编写
        识别输入 → 准备源文件 → 校验 script ↻ → 校验 outline ↻
        → ■ checkpoint_plan

阶段 2  网页开发
        scaffold → 移除示例章 → 构建第 1 章 ↻ → ■ checkpoint_ch1
        → 构建第 2…N 章 ↻ → ■ checkpoint（按模式 A/B/C）

阶段 3  音频合成（可选）
        ■ checkpoint_audio → 提取旁白
        → ■ checkpoint_segments → TTS 合成

阶段 4  录屏
        录屏指引 → END
```

| 阶段 | Agent 做什么 | 人在何处确认 |
|:---:|:---|:---|
| **1** | 按风格/格式守卫生成 script + outline | 确认计划、主题、开发模式 |
| **2** | 脚手架 + 按工艺规则写章节 TSX/CSS | 验收第 1 章，再验收 N / 批量 |
| **3** | 旁白提取 + TTS | 可选音频与片段编辑 |
| **4** | 录屏清单 | — |

章节构建内嵌的工艺约束：一步一意 · 隐藏式 Chrome · 内容驱动动画优先于入场动效 · 多点揭示必须一步一项 · 动画时长 ≤ 旁白时长（auto 模式在 `ended` 时推进）。

---

## 仓库结构

```text
ezto_video/
├── ezto-agent/                      # 运行时产品
│   ├── src/backend/                 # FastAPI · 服务 · SSE
│   ├── src/harness/                 # LangGraph 状态机 + Agent
│   ├── src/frontend/                # 工作流控制台（Vite + React）
│   ├── assets/                      # 模板 · 23 主题 · 参考文档
│   ├── runtime/                     # logs · cache · workspace
│   └── tests/                       # backend · harness · flow_parity
├── skills/web-video-presentation/   # 方法论真相源（SKILL.md）
├── docs/                            # 设计文档 + figures/
│   └── figures/                     # ← 截图与架构图放这里
└── CLAUDE.md                        # 本仓库的 Agent 工作说明
```

---

## 快速开始

### 后端（推荐 WSL + conda）

```bash
conda create -n ezto python=3.12 -y && conda activate ezto
cd ezto-agent && pip install -e .
cp .env.example .env   # 填写 DEEPSEEK_API_KEY 等

cd src
uvicorn backend.api.server:app --reload --port 8001
curl http://localhost:8001/health
```

一键配置：`bash ezto-agent/scripts/setup_wsl.sh`

### 前端

```bash
cd ezto-agent/src/frontend
npm install && npm run dev     # http://localhost:5173
```

### 脚手架演示工程内

```bash
cd presentation
npm run dev                    # 预览 · 默认 :5202
npx tsc --noEmit
npm run extract-narrations
npm run synthesize-audio
```

### 最小 API 流程

```bash
curl -X POST http://localhost:8001/api/workflow/start \
  -H "Content-Type: application/json" \
  -d '{"user_request": "你的文章或口播稿...", "language": "zh-CN"}'

curl http://localhost:8001/api/workflow/<thread_id>

curl -X POST http://localhost:8001/api/workflow/<thread_id>/resume \
  -H "Content-Type: application/json" \
  -d '{"confirmations": {"checkpoint_plan": {"selected_theme": "midnight-press", "development_mode": "A"}}}'
```

<details>
<summary><b>API 一览</b></summary>

<br/>

| 方法 | 路径 | 用途 |
|:---:|:---|:---|
| POST | `/api/workflow/start` | 启动工作流 |
| POST | `/api/workflow/{id}/resume` | 从中断恢复 |
| GET | `/api/workflow/{id}` | 查询状态 |
| GET | `/api/workflow/{id}/events` | SSE 事件流 |
| GET | `/api/workflow/{id}/artifacts` | 列出产出 |
| GET | `/api/workflow/{id}/artifact/{path}` | 读取产出 |
| GET | `/api/themes` | 列出主题 |
| GET | `/health` | 健康检查 |

</details>

---

## 演示模型 · 产出合约

| | |
|:---|:---|
| **舞台** | 按 1920×1080 创作，`transform: scale()` 适配视口 |
| **光标** | 全局 `(chapter, step)`；章节是 `step` 的纯函数 |
| **真相源** | `narrations.ts` 长度 ≡ 步骤数 |
| **播放** | `manual` · `audio` · `auto` |
| **主题** | 23 套 CSS 自定义属性；章节代码无硬编码颜色/字体 |

---

## 文档

| 文档 | 内容 |
|:---|:---|
| [`skills/web-video-presentation/SKILL.md`](skills/web-video-presentation/SKILL.md) | 完整方法论（图需保持对等） |
| [`docs/web_video_graph_guide.md`](docs/web_video_graph_guide.md) | 图结构指南 |
| [`docs/skill-flow-parity.md`](docs/skill-flow-parity.md) | Skill ↔ LangGraph 对等性 |
| [`docs/checkpoint_plan_flow.md`](docs/checkpoint_plan_flow.md) | Checkpoint Plan 交互 |
| [`docs/code-mapping.md`](docs/code-mapping.md) | 代码映射 |
| [`docs/figures/`](docs/figures/) | 截图与架构图投放区 |

---

## 引用

```bibtex
@software{ezto_video,
  title        = {ezto\_video: 面向点击驱动网页视频演示的 Agent 工作流},
  author       = {ezto\_video contributors},
  year         = {2026},
  url          = {https://github.com/YOUR_ORG/ezto_video}
}
```

---

<div align="center">

<pre style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;letter-spacing:0.08em;color:#A3A3A3;line-height:2;">
方法论在 Skill · 执行在 Graph · 人停在 Checkpoint
</pre>

</div>
