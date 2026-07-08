# Anchor: list-reveal（列举型逐个揭示）

> ⚠️ **这是结构示意，不是抄袭模板**。先读 [`../../CHAPTER-CRAFT.md`](../../CHAPTER-CRAFT.md)
> 文档索引 + [#list-reveal-one-per-step](../../CHAPTER-CRAFT.md#list-reveal-one-per-step)。
> 本 anchor 给的是"列举型章节的结构骨架"（单网格 N 槽位 +
> 每 step 只填一个槽位 + 位置不重排）——**实现时用 `ListGrid` + `GridSlot`**。
> 倒过来照抄 = [#no-ai-slop](../../CHAPTER-CRAFT.md#no-ai-slop) 同质化反模式。

## 定位

口播说"三件事 / 四个原因 / N 个特性"时，**每项 1 step 逐个揭示**。
视频中段最常用的章节类型，**最容易翻车成 PPT** —— 这是为什么需要 anchor。

## 适用场景

- "<主体> 强在哪 → 三件事"
- "选购 <X> → 四个角度"
- "为什么我喜欢 <X> → 五个理由"
- 任何"主题 + N 个并列子项"的结构

## 假设的 outline.md 章节段（抽象）

```markdown
## 4. <chapter-id> — <主题 N 件事>（N+1 steps）

- step 1 (~3s) — 引子"<N 件事>" [intent: intro / transition]
- step 2 (~6s) — 第 1 件：<标题> + <article 抽来的细节> [intent: list-reveal]
- step 3 (~6s) — 第 2 件：<标题> [intent: list-reveal]
- ...
- step N+1 (~6s) — 第 N 件：<标题> [intent: list-reveal]
```

## 关键节奏决策

| step | 视觉布局 |
|---|---|
| 1 | `lx-stack-center` 引子大字 + ghost 序号占位 |
| 2 | `GridSlot` "01" active；其余 ghost |
| 3 | "02" active；01 past；其余 ghost |
| ... | 当前 active；之前 past；之后 ghost |

## [#list-reveal-one-per-step](../../CHAPTER-CRAFT.md#list-reveal-one-per-step) 的核心实现

> "布局不重排，只是单元格内容变化"

整个章节只有**一个 `ListGrid`**，N 个 `GridSlot` 节点位置完全不变。
变的只是每个槽位的 `state`（ghost / active / past）。

**反模式**：每点一次重新渲染整个布局 → 已揭示的项也跟着抖动 / 重新
入场 → 观众不知道该看哪。

## 文件结构

```
list-reveal/
├── README.md
├── chapter.tsx     ← SceneChrome + ListGrid + GridSlot
└── chapter.css     ← ch-lr-* 动画 optional
```

## 关键手段（地板线）

| 维度 | 这个 anchor 怎么实现 |
|---|---|
| 布局 | `SceneChrome` + `ListGrid` + `GridSlot state=…` |
| 字号 | `lx-title` / `lx-subtitle` / `lx-body` 角色 |
| 槽位状态 | ghost → active（accent + drop）→ past（dimmed） |
| 动画 | `ch-lr-num-drop` 可选；主样式在 `layouts.css` |

> **新写章节时**：优先复制 `01-example/` grid-3 step，再参考本 anchor 节奏。

## 切到其它主题时

- `bauhaus-bold` → 序号换 Archivo Black + 大色块；用 hard-cut 砸下
- `terminal-green` → 序号 `[01]` `[02]` `[03]` 风格；打字机入场
- `chalk-garden` → 粉笔下划线手绘 + wiggle 入场
- `midnight-press` → 数字 blur clear 慢锐化 + 暖橙光晕慢呼吸

**结构不变**：N+1 step、单网格 N 槽位、每 step 只填一个槽位。

## 想看具象题材应用

- 科技测评 / 实测对比类视频用这个 anchor 长什么样 →
  [`../case-tech-review/outline-snippet.md`](../case-tech-review/outline-snippet.md)
  里 `## 2. why-strong` 章节
