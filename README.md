<div align="center">

# ezto_video

把文章做成可点击播放的网页演示

[![LangGraph](https://img.shields.io/badge/LangGraph-OK-1C3C3C)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-8001-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React%20%2B%20Vite-5173-61DAFB?logo=react&logoColor=black)](https://vitejs.dev/)

</div>

<br/>

<p align="center">
  <img src="docs/figures/teaser.svg" alt="流程总览" width="92%"/>
</p>

---

## 项目说明

用户上传一篇文章后，系统会按固定流程把它做成点击驱动的 16:9 React 演示网页。关键步骤会停下来交给人审核；内容和代码都会按事先定好的规范 / 清单反复检查、修改，直到达标。

实现上是一套 LangGraph 工作流，外面是 FastAPI + React 控制台。规范源头在 `skills/web-video-presentation/`。

---

## 流程

### 上传文章

从控制台新建项目，上传或粘贴文章。

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/figures/ui-home.png" alt="首页" width="100%"/>
      <br/><sub>首页</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/figures/ui-new-project.png" alt="新建项目" width="100%"/>
      <br/><sub>新建项目</sub>
    </td>
  </tr>
</table>

### 第一阶段：脚本和大纲

根据上传的文章拆分章节，生成逐章节的脚本和大纲。大模型会按规范要求不断检测、修改，直到达标，再交给用户审核。

<p align="center">
  <img src="docs/figures/ui-checkpoint-plan.svg" alt="审核脚本大纲" width="88%"/>
</p>
<p align="center"><sub>用户审核脚本 / 大纲</sub></p>

### 第二阶段：搭建第一章

多个 sub-agent 根据第一章大纲搭建对应的演示网页（React）。开发和自检清单是提前规定好的：改代码、跑通网页、再检查，循环到清单里的要求都完成，再交给用户确认。

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/figures/ui-chapter-build.png" alt="搭建网页" width="100%"/>
      <br/><sub>搭建过程</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/figures/ui-chapter-review.png" alt="确认章节" width="100%"/>
      <br/><sub>确认第一章</sub>
    </td>
  </tr>
</table>

### 第三阶段：完成剩余章节

后面的章节参照第一章进行开发，直到整份 slide 网页做完。

<table>
  <tr>
    <td width="33%" align="center">
      <img src="docs/figures/result-presentation.svg" alt="演示页" width="100%"/>
      <br/><sub>演示页</sub>
    </td>
    <td width="33%" align="center">
      <img src="docs/figures/result-steps.svg" alt="逐步点击" width="100%"/>
      <br/><sub>逐步点击</sub>
    </td>
    <td width="33%" align="center">
      <img src="docs/figures/result-themes.svg" alt="主题" width="100%"/>
      <br/><sub>主题</sub>
    </td>
  </tr>
</table>

之后还可以选做音频合成（TTS）和录屏指引，不是主流程的必经步骤。

<p align="center">
  <img src="docs/figures/ui-audio.svg" alt="音频" width="70%"/>
</p>
<p align="center"><sub>音频（可选）</sub></p>

---

## 架构

<p align="center">
  <img src="docs/figures/architecture.svg" alt="架构图" width="88%"/>
</p>

```text
React 前端  ← REST / SSE →  FastAPI (:8001)
                                │
                                ▼
                         LangGraph 工作流
                                │
                                ▼
                    presentation/（Vite + React 演示页）
```

流程图也可以看 [`docs/graph-cn.png`](docs/graph-cn.png)。

演示页本身的约定：

- 内容按 1920×1080 写，再缩放适配视口
- 用全局的 `(章节, 步骤)` 控制进度，点一下走一步
- `narrations.ts` 的长度和步骤数一致
- 播放模式：手动 / 带音频 / 自动推进
- 23 套主题，用 CSS 变量切换，章节代码里不写死颜色

---

## 目录结构

```text
ezto_video/
├── ezto-agent/                      # 后端、工作流、前端
│   ├── src/backend/                 # FastAPI
│   ├── src/harness/                 # LangGraph 与 agent
│   ├── src/frontend/                # 控制台
│   ├── assets/                      # 模板、主题、规范文档
│   └── runtime/                     # 日志、缓存、工作区
├── skills/web-video-presentation/   # Skill 规范
└── docs/figures/                    # README 截图
```

---

## 启动

### 后端（WSL + conda）

```bash
conda create -n ezto python=3.12 -y && conda activate ezto
cd ezto-agent && pip install -e .
cp .env.example .env   # 填写 DEEPSEEK_API_KEY 等

cd src
uvicorn backend.api.server:app --reload --port 8001
```

一键配置：`bash ezto-agent/scripts/setup_wsl.sh`

### 前端

```bash
cd ezto-agent/src/frontend
npm install && npm run dev   # http://localhost:5173
```

### 生成后的演示项目

```bash
cd presentation
npm run dev                  # 默认 :5202
npx tsc --noEmit
```

<details>
<summary>API</summary>

| 方法 | 路径 | 说明 |
|:---:|:---|:---|
| POST | `/api/workflow/start` | 启动工作流 |
| POST | `/api/workflow/{id}/resume` | 审核通过后继续 |
| GET | `/api/workflow/{id}` | 查询状态 |
| GET | `/api/workflow/{id}/events` | SSE 事件流 |
| GET | `/api/workflow/{id}/artifacts` | 列出产出文件 |
| GET | `/api/themes` | 主题列表 |
| GET | `/health` | 健康检查 |

</details>

---

## 相关文档

- [`skills/web-video-presentation/SKILL.md`](skills/web-video-presentation/SKILL.md) — 完整规范
- [`docs/web_video_graph_guide.md`](docs/web_video_graph_guide.md) — 图结构说明
- [`docs/figures/`](docs/figures/) — 截图目录
