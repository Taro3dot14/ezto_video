# Theme Kit 规范（v2）

> 开发者文档 — 如何新增一套 **Theme v2** 主题包。
> Agent 读各主题内的 `kit/COMPONENT-KIT.md`，**不**修改 CHAPTER-CRAFT.md。

## v1 vs v2

| | v1（legacy，23 套内置） | v2（新方案） |
|---|---|---|
| `theme.json` | 无 `schema` 或 `"schema": "v1"` | `"schema": "v2"` |
| 资产 | `tokens.css` | `tokens.css` + `kit/` |
| scaffold | 只安装 tokens | tokens + kit CSS + COMPONENT-KIT.md |
| 换肤 API | 覆盖 tokens | tokens + kit 全套 |
| 组件 | `base.css` primitives + `lx-*` | 上述 + 统一 `tk-*` API |

## 目录结构

```
themes/<id>/
├── theme.json
├── tokens.css
└── kit/
    ├── COMPONENT-KIT.md    # Agent 读本主题的组件标准
    ├── components.css    # tk-* 实现
    ├── presets.css         # mot-tk-* 动效（可选）
    └── fonts.css           # 主题字体 import（可选）
```

## theme.json 必填字段（v2）

```json
{
  "id": "clay-warm",
  "schema": "v2",
  "name": "Clay Warm",
  "nameZh": "暖陶塑",
  "family": "claymorphism",
  "description": "...",
  "descriptionZh": "...",
  "mood": [],
  "bestFor": [],
  "kit": {
    "components": "kit/components.css",
    "presets": "kit/presets.css",
    "fonts": "kit/fonts.css",
    "guide": "kit/COMPONENT-KIT.md"
  },
  "capabilities": ["tk-card", "tk-badge", "..."],
  "preview": { "shell": "#...", "surface": "#...", "text": "#...", "accent": "#..." }
}
```

## 共享 tk-* 词汇表

所有 v2 主题应实现**同一语义 API**，视觉由各自 `components.css` 决定：

| Class | 语义 |
|-------|------|
| `tk-card` | 主内容卡片 |
| `tk-badge` | 状态胶囊 |
| `tk-chip` | 关键词标签 |
| `tk-button` | 装饰性 CTA |
| `tk-stat` | 大数字指标 |
| `tk-icon-tile` | SVG 图标容器 |
| `tk-callout` | 提示框 |
| `tk-window` | 终端/代码窗 chrome |
| `tk-progress` | 粗进度条 |
| `tk-slot` | GridSlot 皮肤修饰 |

章节组合：`className="lx-split-panel tk-card"` — layout + material。

## 材质 Token（tokens.css 可覆盖 base.css 默认值）

```css
--tk-border-w, --tk-r-sm/md/lg, --tk-lift
--tk-border, --tk-shadow
--tk-shadow-raised, --tk-shadow-pressed, --tk-shadow-inset
--dur-tk-press, --ease-tk
```

## 安装流程

**scaffold.sh**（`--theme=<id>`）：

1. 复制 `templates/` 内核
2. 复制 `tokens.css`
3. 若 `schema=v2`：覆盖 `theme-kit.css`、`theme-presets.css`、`theme-fonts.css`，写入 `src/theme/COMPONENT-KIT.md`
4. 写入 `.theme` JSON manifest

**theme_service.apply_theme**（运行时换肤）：同上，由 `harness.services.theme_kit` 执行。

## Agent 接入

- `read_chapter_context` 自动附带 v2 的 COMPONENT-KIT.md
- `chapter_brief` 通用提示：存在 kit 时优先 `tk-*`
- CHAPTER-CRAFT.md **不变**

## 已有 v2 主题

| id | family | 材质 |
|---|---|---|
| `clay-warm` | claymorphism | 厚边框 + 双阴影 + 暖陶 |
| `dune-ridge` | gallery-restraint | 细线 + paper-lift + 沙丘画廊（替代隐藏的 v1 `dune`） |

隐藏旧主题：在旧版 `theme.json` 设 `"hidden": true`（可选 `"replacedBy": "<new-id>"`）。`list_themes` / scaffold `/api/themes` 会跳过。

## 新增主题 checklist

- [ ] `theme.json` schema=v2 + capabilities
- [ ] `tokens.css` 调色板 + 材质 token
- [ ] `kit/components.css` 实现 tk-* API
- [ ] `kit/COMPONENT-KIT.md` 用法与禁忌
- [ ] `kit/presets.css`（可选 mot-tk-*）
- [ ] `kit/fonts.css`（可选）
- [ ] 对比度：正文 `--text` on `--surface` ≥ 4.5:1
- [ ] 本地 scaffold `--theme=<id>` + typecheck
