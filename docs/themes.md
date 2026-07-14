# 演示网页主题

演示网页内置 **23** 套主题。每套是独立的 CSS token + `theme.json`，不是简单换色。

- 源文件：[`ezto-agent/assets/themes/`](../ezto-agent/assets/themes/)
- 主题契约：[`ezto-agent/assets/references/THEMES.md`](../ezto-agent/assets/references/THEMES.md)

---

## 深色

| id | 名称 | 说明 |
|----|------|------|
| `midnight-press` | 暗色印刷 | 暖色 espresso 暗底 + 火热橙，电影感编辑气质 |
| `chalk-garden` | 粉笔花园 | 深石板黑板 + 手写字体 + 粉笔黄，虚线 rule 签名 |
| `terminal-green` | 终端绿 | 磷光终端：纯黑 + 等宽字体 + CRT 扫描线 |
| `blueprint` | 蓝图 | 工程蓝图：海军蓝 + 绘图青 + 制图网格 |
| `dark-botanical` | 暗夜植物 | 时尚刊物暗底，柔光晕染，慢节奏 |
| `neon-cyber` | 霓虹赛博 | 赛博朋克：电光青 + 玫红双霓虹 |
| `bold-signal` | 焦点信号 | Pitch deck 暗底，大橙色焦点，大字标语 |
| `creative-voltage` | 电压创意 | 电光蓝底 + 霓虹黄，halftone 网点 |

## 浅色

| id | 名称 | 说明 |
|----|------|------|
| `paper-press` | 浅色印刷 | midnight-press 的白天版，暖奶油 + 纸纹 |
| `warm-keynote` | 暖色 Keynote | 现代 SaaS keynote，大圆角 glass slab |
| `newsroom` | 新闻室 | 报刊风：报纸奶油 + 旗红，0 圆角 |
| `bauhaus-bold` | 包豪斯 | 米白 + 原色蓝，厚边框 + 偏移实色阴影 |
| `sunset-zine` | 日落 Zine | risograph zine：暖桃 + 洋红 |
| `monochrome-print` | 黑白印刷 | 精炼印刷杂志，极简发丝线 |
| `vintage-editorial` | 复古编辑 | 奶油底 + Fraunces，细线几何叠层 |
| `pastel-dream` | 粉彩梦 | 柔粉蓝灰，大圆角 + pill 色条 |
| `split-canvas` | 双拼画布 | 蜜桃 / 薰衣草 50/50 硬切分 |
| `electric-studio` | 电光商业 | 净白 + 电光蓝，贴底色条 |
| `indigo-porcelain` | 靛蓝瓷 | 靛蓝当墨 + 瓷白纸，学术气质 |
| `forest-ink` | 森林墨 | 森林绿当墨 + 象牙白纸 |
| `kraft-paper` | 牛皮纸 | 深棕当墨 + 牛皮米，粗纸纹 |
| `dune-ridge` | 沙丘 | 炭褐当墨 + 沙底，画廊感宽 padding |
| `swiss-ikb` | 瑞士国际主义 | 极细字重 + IKB 蓝 + 发丝网格 |

> 旧版 `dune` 已隐藏，由 `dune-ridge` 取代。

---

## 选用

在工作流「核对清单」里选主题；脚手架也可指定：

```bash
bash <scaffold.sh> --theme midnight-press
```

列出可用主题：

```bash
bash <scaffold.sh> --list-themes
```
