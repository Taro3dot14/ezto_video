# Anchor: hook-chapter（钩子型开场）

> ⚠️ **这是结构示意，不是抄袭模板**。先读 [`../../CHAPTER-CRAFT.md`](../../CHAPTER-CRAFT.md)
> 文档索引 + [#visual-demos-required](../../CHAPTER-CRAFT.md#visual-demos-required)。
> 本 anchor 给的是"钩子型开场的结构骨架"——保留 step 切分逻辑、字号关系，
> **实现时用 SceneChrome + lx-\* shell**（见 `chapter.tsx`）。
> 倒过来照抄 = [#no-ai-slop](../../CHAPTER-CRAFT.md#no-ai-slop) 同质化反模式。

## 定位

视频开头最常用的章节类型：**抛 N 张可疑图 / 反例 / 截图 → 引出主题 →
切大字 hero takeover**。

## 适用场景

- 悬念型开头：先甩 3~4 张让人怀疑 / 困惑的图，再揭示原因
- "今天聊聊 X 的几个翻车现场"：先看翻车，再切主题
- 产品发布的"问题感"开场：先看痛点截图，再揭示新功能

## 假设的 outline.md 章节段（抽象）

```markdown
## 2. hook — <章节标题>（6 steps）

- step 1 (~4s) — N 张可疑图片占位（虚线 ghost 卡片） [intent: intro / transition]
- step 2 (~5s) — 第 1 张露出：<反例 1 描述>（独占视觉） [intent: solo reveal]
- step 3 (~5s) — 第 2 张露出：<反例 2 描述> [intent: solo reveal]
- step 4 (~5s) — 第 3 张露出：<反例 3 描述> [intent: solo reveal]
- step 5 (~4s) — 三张缩入侧栏，中间出 <主题大字> takeover [intent: hero opener]
- step 6 (~3s) — 切到下一句钩子（brush 划掉） [intent: quote close]
```

## 关键节奏决策

| step | 节奏意图 | Shell / 视觉 |
|---|---|---|
| 1 | 抛悬念 —— N 张未知 | `lx-stack` + `lx-grid-3` ghost 卡片 |
| 2-N | **每张图独占视觉** | `lx-solo` 大图 ~70% + caption |
| N+1 | takeover —— 揭示主题 | `lx-cover-body` 迷你卡 + hero |
| 末 | 钩子收束 | `lx-quote-body` + brush 动画 |

## 为什么 2-N 不能 stagger 同时上

口播会**逐个念出来** —— 必须 1 项 = 1 step（[§ 逐步揭示](../../CHAPTER-CRAFT.md#list-reveal-one-per-step)）。
同时 stagger 上 = 观众扫一眼看完，讲者还在念第一张 = PPT 直觉。

## 文件结构

```
hook-chapter/
├── README.md       ← 本文件
├── chapter.tsx     ← SceneChrome + lx-* 结构骨架
└── chapter.css     ← ch-hk-* 动画 only
```

## 关键手段（地板线）

| 维度 | 这个 anchor 怎么实现 |
|---|---|
| 布局 | `SceneChrome` + `lx-stack` / `lx-solo` / `lx-cover` / `lx-quote` |
| 素材 | `<img src="/hook/<asset>.png" />` 真截图 |
| 字号 | `lx-hero` / `lx-body` 角色（见 LAYOUT-SYSTEM.md） |
| 动画 | `ch-hk-*` in chapter.css（stamp / bar / brush） |
| takeover | 三张图缩入 + hero 巨字 + accent 红条 |

> **新写章节时**：优先复制 `01-example/`，再参考本 anchor 的节奏。
> 持续微动按需挂 —— 见 [#no-ai-slop](../../CHAPTER-CRAFT.md#no-ai-slop)。

## 切到其它主题时

- `bauhaus-bold` → brush 划掉换 hard-cut 大色块；hero 字体换 Archivo Black
- `terminal-green` → 三张图换"FILE_001/002/003"占位框；hero 用打字机
- `chalk-garden` → 粉笔感虚线 + 慢速 wiggle 入场
- `midnight-press` → blur clear 慢镜入场 + ken burns + scanline

**结构（N+2 步、独占节奏、takeover、收束）保持不变。**

## 想看具象题材应用

- 科技测评 / 实测对比类视频用这个 anchor 开场长什么样 →
  [`../case-tech-review/`](../case-tech-review/)
