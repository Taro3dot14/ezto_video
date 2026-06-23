# web-video-presentation 流程固化文档

> 用途：LangGraph 实现的单一日标源。所有节点、边、interrupt、guard、artifact 路径均基于此文档实现。
> 来源：`skills/web-video-presentation/SKILL.md` + `references/`
> 注意：本文档记录原始设计目标。实际实现请参照 `code-mapping.md`，部分节点拆分和路由细节已在实现中调整。

---

## 1. 原流程摘要

```text
Phase 1 内容编写
  1.1 识别用户输入
  1.2 一次产出 script.md + outline.md
  自检 script.md (SCRIPT-STYLE.md)
  自检 outline.md (OUTLINE-FORMAT.md)
  ↓
Checkpoint Plan — 必须停，一次对齐 5 件事：
  口播稿 / outline / 主题 / 素材 / 开发模式
  ↓
Phase 2 网页开发
  2.1 脚手架 scaffold (选定主题)
  2.2 第 1 章 = 主线程完整版本 (强制 anchor)
  第 1 章强制验收 — 必须停
  2.3 第 2~N 章按模式 A / B / C
  2.4 每章实现必须读 CHAPTER-CRAFT.md
  2.5 大改后 bump STORAGE_KEY
  ↓
Checkpoint Audio — 必须停，是否合成音频
  ↓
Phase 3 音频合成 (可选)
  extract-narrations → audio-segments.json → 用户检查 → synthesize
  ↓
Phase 4 录屏 + 后期
  auto 模式 或 manual 模式
```

---

## 2. 节点映射表

| # | 原流程 | LangGraph 节点 | interrupt | required refs | 前置条件 | 输出文件 |
|---|---|---|---:|---|---|---|
| 1 | 识别用户输入 | `wv_identify_input` | 否 | — | START | `input_type` (article/script/none) |
| 2 | 产出初稿 | `wv_prepare_source_files` | 否 | `SCRIPT-STYLE.md`, `OUTLINE-FORMAT.md` | input_type ≠ none | `article.md?`, `script.md`, `outline.md` |
| 3 | script 自检 | `wv_validate_script` | 否 | `SCRIPT-STYLE.md` | script.md 存在 | validation_result |
| 4 | script 修复 | `wv_repair_script` | 否 | `SCRIPT-STYLE.md` | validation fail | revised `script.md` |
| 5 | outline 自检 | `wv_validate_outline` | 否 | `OUTLINE-FORMAT.md` | outline.md 存在 | validation_result |
| 6 | outline 修复 | `wv_repair_outline` | 否 | `OUTLINE-FORMAT.md` | validation fail | revised `outline.md` |
| 7 | **Checkpoint Plan** | `wv_checkpoint_plan` | **是** | themes metadata | Phase 1 完成 | 用户确认 5 件事 |
| 8 | 脚手架 | `wv_scaffold_presentation` | 否 | `THEMES.md` (custom theme) | 主题已选定 | `presentation/` 目录 |
| 9 | 删除 demo | `wv_remove_example_chapter` | 否 | — | scaffold 完成 | clean scaffold |
| 10 | 第 1 章实现 | `wv_build_chapter_1` | 否 | `CHAPTER-CRAFT.md`, theme.json | scaffold 就绪 | chapter 1 files |
| 11 | 第 1 章自检 | `wv_validate_chapter_1` | 否 | `CHAPTER-CRAFT.md` | chapter 1 完成 | validation_result |
| 12 | 第 1 章修复 | `wv_repair_chapter_1` | 否 | `CHAPTER-CRAFT.md` | validation fail | revised chapter 1 |
| 13 | **第 1 章验收** | `wv_checkpoint_chapter_1` | **是** | — | chapter 1 pass | 用户反馈 |
| 14 | 选择开发模式 | `wv_select_development_mode` | 否 | — | chapter 1 验收通过 | mode: A / B / C |
| 15 | 第 N 章实现 + 自检 + 修复 | `wv_build_chapter_n` → `wv_validate_chapter_n` → `wv_repair_chapter_n` (循环) | 否 | `CHAPTER-CRAFT.md` (每章 reload) | mode = A/B/C | chapter N files |
| 16 | 递增章节索引 | `wv_increment_chapter_index` | 否 | — | 验证通过 | current_chapter_index++ |
| 17 | **模式 A: 逐章验收** | `wv_checkpoint_chapter_n` | **每章是** | — | mode = A | 用户确认继续/停止 |
| 18 | **模式 B/C: 批量验收** | `wv_checkpoint_remaining_batch` | **最后是** | — | mode = B/C | 用户确认批次 |
| 19 | STORAGE_KEY 检查 | `wv_transition_to_phase3` | 否 | — | 所有章节完成 | possible edit |
| 16 | STORAGE_KEY 检查 | `wv_transition_to_phase3` | 否 | — | 所有章节完成 | possible edit |
| 17 | **Checkpoint Audio** | `wv_checkpoint_audio` | **是** | — | Phase 2 完成 | yes / no |
| 18 | 抽出 narrations | `wv_extract_narrations` | 否 | `AUDIO.md` | 用户选择合成 | `audio-segments.json` |
| 19 | **检查 segments** | `wv_checkpoint_audio_segments` | **是** | `AUDIO.md` | segments 生成 | approve / edit |
| 20 | 合成音频 | `wv_synthesize_audio` | 否 | `AUDIO.md` | segments approve | `public/audio/` mp3s |
| 21 | 音频异常报告 | `wv_report_audio_anomalies` | 否 | — | 合成完成 | anomaly summary |
| 22 | 录屏路径说明 | `wv_recording_guidance` | 否 | `RECORDING.md` | Phase 3 完成 / 跳过 | final guidance |

### 节点间条件边

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
| `wv_select_development_mode` | 还有剩余章 | `wv_build_chapter_n` |
| `wv_select_development_mode` | 无剩余章 | `wv_transition_to_phase3` |
| `wv_validate_chapter_n` | pass, mode A | `wv_checkpoint_chapter_n` |
| `wv_validate_chapter_n` | pass, mode B/C, 还有章 | `wv_increment_chapter_index` |
| `wv_validate_chapter_n` | pass, mode B/C, 无章 | `wv_checkpoint_remaining_batch` |
| `wv_validate_chapter_n` | fail (≤3 次) | `wv_repair_chapter_n` |
| `wv_validate_chapter_n` | fail (>3 次) | mode 路由 (强制通过) |
| `wv_repair_chapter_n` | 总是 | `wv_validate_chapter_n` |
| `wv_checkpoint_chapter_n` | 继续 & 还有章 | `wv_increment_chapter_index` |
| `wv_checkpoint_chapter_n` | 停止或无章 | `wv_transition_to_phase3` |
| `wv_increment_chapter_index` | 还有章 | `wv_build_chapter_n` |
| `wv_increment_chapter_index` | 无章 | `wv_transition_to_phase3` |
| `wv_checkpoint_audio` | yes | `wv_extract_narrations` |
| `wv_checkpoint_audio` | no | `wv_recording_guidance` |

---

## 3. Required Refs 表

| 阶段 | 必须读取的文件 | 读取时机 | 校验点 |
|---|---|---|---|
| Phase 1.2 写稿 | `SCRIPT-STYLE.md` | `wv_prepare_source_files` 节点内 | `ref_loader` 记录 |
| Phase 1.2 写 outline | `OUTLINE-FORMAT.md` | `wv_prepare_source_files` 节点内 | `ref_loader` 记录 |
| Phase 2.1 脚手架 | `THEMES.md` (自定义主题时) | `wv_scaffold_presentation` 节点内 | 可选 |
| Phase 2.4 每章实现 | `CHAPTER-CRAFT.md` | 每次 `wv_build_chapter_N` 节点内 | 必须 reload |
| Phase 3 音频合成 | `AUDIO.md` | `wv_extract_narrations` / `wv_synthesize_audio` | `ref_loader` 记录 |
| Phase 4 录屏 | `RECORDING.md` | `wv_recording_guidance` 节点内 | `ref_loader` 记录 |

### 禁止行为

| 禁止行为 | Guard 拦截点 | 期望行为 |
|---|---|---|
| 未读 `CHAPTER-CRAFT.md` 就写章节 | `wv_build_chapter_N` 入口 | 抛出 PolicyViolation |
| 启动时一次性读所有 references | `ref_loader` | 按阶段按需加载 |
| 跳过 checkpoint 直接推进 | 每个 interrupt 节点 | 必须等用户 resume |
| 第 1 章并行化 | 模式选择时强制串行 | 第 1 章只能主线程 |

---

## 4. Artifact 契约

### 4.1 工作区目录结构

```text
workspace/{thread_id}/
├── article.md                  # 用户给原文时保留
├── script.md                   # 平台化口播稿
├── outline.md                  # 开发计划
└── presentation/               # Vite + React + TS 脚手架项目
    ├── src/
    │   ├── chapters/
    │   │   └── {NN}-{id}/
    │   │       ├── {Chapter}.tsx
    │   │       ├── {Chapter}.css
    │   │       └── narrations.ts   # step 数 + 口播文本唯一真相源
    │   └── registry/
    │       └── chapters.ts         # 章节注册表
    ├── scripts/
    │   ├── extract-narrations.ts
    │   ├── synthesize-audio.sh
    │   └── tts-providers/
    │       ├── minimax.sh
    │       └── openai.sh
    ├── audio-segments.json         # Phase 3 生成
    └── public/audio/{id}/{N}.mp3   # Phase 3 合成
```

### 4.2 文件契约

| 文件 | 创建节点 | 必须存在 | 说明 |
|---|---|---|---|
| `article.md` | `wv_prepare_source_files` | 用户给原文时 | 不删，画面信息源 |
| `script.md` | `wv_prepare_source_files` | 是 | 保持原文语言的平台化口播稿 |
| `outline.md` | `wv_prepare_source_files` | 是 | 章节切分 + step 内容 + 信息池 |
| `presentation/` | `wv_scaffold_presentation` | 是 | Vite + React + TS 项目 |
| `presentation/src/chapters/{NN}-{id}/narrations.ts` | `wv_build_chapter_N` | 每章 | 数组长度 = step 数 |
| `audio-segments.json` | `wv_extract_narrations` | Phase 3 时 | 合成前 review |
| `public/audio/{id}/{N}.mp3` | `wv_synthesize_audio` | Phase 3 后 | 每步音频文件 |

---

## 5. Interrupt 契约

| interrupt 节点 | type payload | 必须包含的信息 | 用户返回内容 |
|---|---|---|---|
| `wv_checkpoint_plan` | `checkpoint_plan` | script 路径, outline 路径, 主题推荐 (2-3), 素材清单, 模式 A/B/C | script 反馈, outline 反馈, 选定主题, 素材方案, 选定模式 |
| `wv_checkpoint_chapter_1` | `checkpoint_chapter_1` | 第 1 章验收清单 (视觉/节奏/动画/双源/反AI) | pass / 修改反馈 |
| `wv_checkpoint_chapter_n` | `checkpoint_chapter_n` | 第 N 章验收清单 | pass / 修改反馈 |
| `wv_checkpoint_remaining_batch` | `checkpoint_remaining` | 已完成章节列表 | pass / 修改反馈 |
| `wv_checkpoint_audio` | `checkpoint_audio` | 当前状态: N 章 M 步, dev server 地址 | yes / no |
| `wv_checkpoint_audio_segments` | `checkpoint_audio_segments` | `audio-segments.json` 内容, 总段数 | approve / edit |

---

## 6. 开发模式分支逻辑

### 模式 A: 逐章确认 (默认)

```text
用户不明确选择时默认走 A
  → for each chapter in range(2, N+1):
      build → validate → repair? → interrupt(accept)
```

### 模式 B: 顺序 + 批量验收

```text
  → for each chapter in range(2, N+1):
      build → validate → repair?
  → interrupt(batch_accept)
```

### 模式 C: 并行 subgraph

```text
  → fan_out:
      for each chapter in range(2, N+1):
        create_subgraph(chapter_N, ctx={
          outline_section, CHAPTER-CRAFT.md, theme.json,
          chapter_1_code_ref, css_prefix, no_modify_chapters_ts
        })
  → fan_in:
      validate_all → repair_failed → interrupt(batch_accept)
```

---

## 7. Golden Trace

### 最小输入 (用户直接给了口播稿 + 2 章, 模式 A, 无音频)

```text
START
wv_identify_input
wv_prepare_source_files
wv_validate_script
wv_validate_outline
  === wv_checkpoint_plan INTERRUPT ===
wv_scaffold_presentation
wv_remove_example_chapter
wv_build_chapter_1
wv_validate_chapter_1
  === wv_checkpoint_chapter_1 INTERRUPT ===
wv_select_development_mode         → A
wv_build_chapter_n                 (chapter 2)
wv_validate_chapter_n
  === wv_checkpoint_chapter_n INTERRUPT ===
wv_increment_chapter_index         (3 → 超出 total=2)
wv_transition_to_phase3
  === wv_checkpoint_audio INTERRUPT ===  → no
wv_recording_guidance
END
```

### 完整流程 (含 Phase 3 + 模式 B)

```text
START
wv_identify_input
wv_prepare_source_files
wv_validate_script
wv_repair_script (fix)
wv_validate_outline
  === wv_checkpoint_plan INTERRUPT ===
wv_scaffold_presentation
wv_remove_example_chapter
wv_build_chapter_1
wv_validate_chapter_1
wv_repair_chapter_1 (fix)
  === wv_checkpoint_chapter_1 INTERRUPT ===
wv_select_development_mode         → B
wv_build_chapter_n                 (chapter 2)
wv_validate_chapter_n
wv_increment_chapter_index         (→ 3)
wv_build_chapter_n                 (chapter 3)
wv_validate_chapter_n
wv_increment_chapter_index         (→ 4, total=3)
  === wv_checkpoint_remaining_batch INTERRUPT ===
wv_transition_to_phase3
  === wv_checkpoint_audio INTERRUPT ===  → yes
wv_extract_narrations
  === wv_checkpoint_audio_segments INTERRUPT ===
wv_synthesize_audio
wv_report_audio_anomalies
wv_recording_guidance
END
```

---

## 8. 完整流程图

```text
START
  │
  ▼
wv_identify_input
  │
  ▼
wv_prepare_source_files
  │  reads: SCRIPT-STYLE.md, OUTLINE-FORMAT.md
  │  creates: article.md?, script.md, outline.md
  │
  ▼
wv_validate_script ──fail──→ wv_repair_script ──→ (back)
  │ pass
  ▼
wv_validate_outline ──fail──→ wv_repair_outline ──→ (back)
  │ pass
  ▼
╔══════════════════════════════════╗
║  wv_checkpoint_plan  INTERRUPT  ║  ← 一次对齐 5 件事
╚══════════════════════════════════╝
  │ resume
  ▼
wv_scaffold_presentation          reads: THEMES.md (custom)
  │
  ▼
wv_remove_example_chapter
  │
  ▼
wv_build_chapter_1                reads: CHAPTER-CRAFT.md, theme.json
  │
  ▼
wv_validate_chapter_1 ──fail──→ wv_repair_chapter_1 ──→ (back)
  │ pass
  ▼
╔══════════════════════════════════╗
║  wv_checkpoint_chapter_1  INTER ║  ← 第 1 章强制验收
╚══════════════════════════════════╝
  │ resume
  ▼
wv_select_development_mode
  │
  ├──→ A: [loop ch2..N]
  │      wv_build_chapter_N   reads: CHAPTER-CRAFT.md (reload)
  │      wv_validate_chapter_N
  │      wv_repair_chapter_N (if fail)
  │    ╔══════════════════════╗
  │    ║ wv_checkpoint_ch_N   ║  ← 每章验收
  │    ╚══════════════════════╝
  │
  ├──→ B: [loop ch2..N, no interrupt]
  │      wv_build_chapter_N
  │      wv_validate_chapter_N
  │      wv_repair_chapter_N (if fail)
  │    ╔══════════════════════╗
  │    ║ wv_checkpoint_batch  ║  ← 批量验收
  │    ╚══════════════════════╝
  │
  └──→ C: [fan-out subgraphs ch2..N]
         each: build → validate → repair
         [fan-in]
       ╔══════════════════════╗
       ║ wv_checkpoint_batch  ║  ← 批量验收
       ╚══════════════════════╝
          │
          ▼
wv_transition_to_phase3
  │
  ▼
╔══════════════════════════════════╗
║  wv_checkpoint_audio  INTERRUPT ║  ← 是否合成音频
╚══════════════════════════════════╝
  │                           │
  │ yes                       │ no
  ▼                           ▼
wv_extract_narrations        (skip)
  │ reads: AUDIO.md
  ▼
╔══════════════════════════════════╗
║  wv_checkpoint_audio_seg INTER  ║  ← review segments
╚══════════════════════════════════╝
  │ resume
  ▼
wv_synthesize_audio
  │ reads: AUDIO.md
  ▼
wv_report_audio_anomalies
  │
  ▼
wv_recording_guidance             reads: RECORDING.md
  │
  ▼
END
```

---

## 9. Validation 自检协议

### script.md 自检项 (来自 SCRIPT-STYLE.md)

| 检查项 | 层级 | 失败处理 |
|---|---|---|
| 保持原文语言 | 形式 | 重写 |
| 平台化口播语气 | 形式 | 重写 |
| 节拍切分合理 | 风骨 | 重切 |
| 信息密度适中 | 风骨 | 删减/拆分 |
| 念出来通顺 | 念出来 | 调整断句 |

### outline.md 自检项 (来自 OUTLINE-FORMAT.md)

| 检查项 | 失败处理 |
|---|---|
| 章节切分合理 | 重新切分 |
| step 数匹配口播节拍 | 增减 step |
| 每章有信息池 | 补充 |
| 末尾有素材清单 | 补充 |

### 单章自检项 (来自 CHAPTER-CRAFT.md Part 7)

| # | 检查项 | 失败处理 |
|---|---|---|
| 1 | 至少 1~2 处 CSS/SVG/Canvas/JS 视觉演示 | 补视觉演示 |
| 2 | 不同 step 的主导动作不一样 | 重做动画 |
| 3 | 字号大、留白舒服、配色舒服 | 调整 |
| 4 | 清单/列表逐个揭示, 1 项 = 1 step | 拆 step |
| 5 | 画面信息比口播稿多 (回了 article 抽细节) | 补细节 |
| 6 | 无紫粉渐变/圆角彩色边框/emoji/假数据 | 替换 |
| 7 | 缺素材用 placeholder, 不是 fake | 换 placeholder |
| 8 | 颜色和字体家族全部走 token | 改 token |
| 9 | 交付时告知用户缺少的素材 | 补充说明 |
| 10 | 无小号字体、无大量纯文字 | 改 |
| 11 | 无页眉页脚 | 删 |
| 12 | `npx tsc --noEmit` 通过 | 修类型错误 |
| 13 | 独立 CSS 前缀、未跨章 import、未改 chapters.ts 外文件 | 修 |
| 14 | `narrations.ts` 存在且长度匹配 step 数 | 修 |
| 15 | 每条 narration 与 `script.md` 语义一致 | 修 |
| 16 | 动画时长 ≤ 口播时长 | 调动画或拆 step |

---

## 10. 文件引用路径常量

```python
# skills/ 目录相对于项目根
SKILL_ROOT = "skills/web-video-presentation"
REFERENCES = f"{SKILL_ROOT}/references"
THEMES_DIR = f"{SKILL_ROOT}/themes"
SCRIPTS_DIR = f"{SKILL_ROOT}/scripts"
TEMPLATES_DIR = f"{SKILL_ROOT}/templates"

REQUIRED_REFS = {
    "phase1": ["SCRIPT-STYLE.md", "OUTLINE-FORMAT.md"],
    "chapter": ["CHAPTER-CRAFT.md"],
    "theme": ["THEMES.md"],
    "audio": ["AUDIO.md"],
    "recording": ["RECORDING.md"],
}

REF_PATHS = {
    "SCRIPT-STYLE.md": f"{REFERENCES}/SCRIPT-STYLE.md",
    "OUTLINE-FORMAT.md": f"{REFERENCES}/OUTLINE-FORMAT.md",
    "CHAPTER-CRAFT.md": f"{REFERENCES}/CHAPTER-CRAFT.md",
    "THEMES.md": f"{REFERENCES}/THEMES.md",
    "AUDIO.md": f"{REFERENCES}/AUDIO.md",
    "RECORDING.md": f"{REFERENCES}/RECORDING.md",
    "scaffold.sh": f"{SCRIPTS_DIR}/scaffold.sh",
}

ARTIFACT_CONTRACT = {
    "article.md": {"phase": 1, "optional": True},
    "script.md": {"phase": 1, "optional": False},
    "outline.md": {"phase": 1, "optional": False},
    "presentation/": {"phase": 2, "optional": False},
    "audio-segments.json": {"phase": 3, "optional": True},
    "public/audio/": {"phase": 3, "optional": True},
}
```
