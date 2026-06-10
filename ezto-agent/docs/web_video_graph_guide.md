# web_video.py 22 节点 LangGraph 详解

## 架构概览

整个工作流图分为 4 个阶段（Phase），对应 SKILL.md 方法论的四个步骤：

```
Phase 1 (内容编写) → Phase 2 (网页开发) → Phase 3 (音频合成) → Phase 4 (录屏)
  7 个节点            11 个节点            5 个节点             1 个节点
```

每个阶段必须完成后才能进入下一个。阶段间的转换通过 **checkpoint 中断** 守卫，等待用户确认。

---

## 节点分类

所有节点按功能分为 4 类：

| 类别 | 数量 | 说明 |
|---|---|---|
| **LLM 生成** | 12 | 调用 `llm.chat()` 调用 DeepSeek 生成或分析内容 |
| **Checkpoint 中断** | 6 | 调用 `interrupts.checkpoint_*()` 暂停工作流等待用户操作 |
| **Shell/工具执行** | 4 | 调用 `tool_adapters` 执行脚手架、npm 脚本、文件操作 |
| **状态转换** | 1 | 纯 state 更新，无 LLM 或 I/O |

所有节点统一由 `_wrap_node()` 包装，自动完成：
- `completed_nodes` 追踪
- `thinking_log` 收集（前端 SSE 流式推送）
- 执行耗时日志
- 异常捕获（`GraphInterrupt` 作为正常中断路径跳过）

---

## Validation-Repair 循环模式

共有 4 个"验证→修复"循环，每个交付物对应一个，模式相同：

```
  ┌─ Build/Prepare ─→ Validate ─→ [pass] ─→ 下一个节点
  │                     │
  │                   [fail]
  │                     │
  └──── Repair ←────────┘
```

路由函数检查最近一次验证结果和修复重试次数。`MAX_REPAIR_RETRIES = 3`，超过后强制 pass 防止死循环。修复历史记录在 `state.repair_history` 中。

---

## 开发模式 A / B

第 1 章完成后用户选择开发模式：

- **模式 A（顺序/交互）**：每章构建后中断工作流，用户确认后再继续。慢但安全。
- **模式 B（批量）**：所有剩余章节一次性构建完成，最后统一确认。

模式影响 `route_chapter_n_validation` 和 `route_mode_a_checkpoint` 的决策逻辑。

---

## 节点详解

### Phase 1 — 内容编写

目标：将用户的原始输入转换为 `script.md` + `outline.md`，验证两者，然后让用户确认方案。

---

#### 1. wv_identify_input

**设计目的**：将用户输入分类为 article（文章）、script（口播稿）或 none（无内容）。分类结果决定后续生成策略。

**思路**：此节点是最简单的 LLM 调用——不需要复杂输出格式，只需要一个单词。使用 `temperature=0.0` 保证确定性。

**代码详解**：
- `< 20 字符` → 直接判为 none，跳过 LLM 调用
- 否则调用 DeepSeek 要求回复一个单词
- 做关键字匹配：先匹配到 "article" 或 "script" 就返回，否则默认 `none`
- 不需要 JSON 解析，没有复杂的 fallback

---

#### 2. wv_prepare_source_files

**设计目的**：一次 LLM 调用同时生成 `script.md`（口播稿）和 `outline.md`（大纲），避免两次往返。

**思路**：使用 `===OUTLINE===` 分隔符将两个文件拼接在同一个回复里，减少一次 LLM 调用和等待时间。加载 `SCRIPT-STYLE.md` 和 `OUTLINE-FORMAT.md` 为参考上下文。

**代码详解**：
- 加载两个参考文件（必须存在，否则抛出 policy violation）
- 如果 `input_type == "none"`，记录错误并跳过生成
- 构建含参考文件和原始输入的 prompt，要求 LLM 生成两部分
- 使用 `.split("===OUTLINE===")` 分隔回复，写入文件
- 将文件路径加入 `created_files`，前端可追踪

---

#### 3. wv_validate_script

**设计目的**：根据 `SCRIPT-STYLE.md` 规则对 `script.md` 进行自检，输出结构化的 JSON 结果。

**思路**：任何交付物在交给用户前必须先自检。JSON 输出格式让路由函数能基于 `passed` 做分支决策。

**代码详解**：
- 加载参考文件，读取 `script.md`
- 提示 LLM 输出 JSON 格式：`{"passed": bool, "failed_checks": [...], "details": "..."}`
- `temperature=0.0` 确保输出稳定
- JSON 解析失败时默认 pass，防止 LLM 输出格式错误导致卡住
- 结果存入 `validation_results`，后续 repair 和 route 都会用到

---

#### 4. wv_repair_script

**设计目的**：修复 `script.md` 的验证问题。使用上一次验证的失败检查项作为修复上下文。

**思路**：典型"错误反馈→重新生成"模式。读取最后一次验证结果中的 `failed_checks` 和 `details`，让 LLM 针对性修复。

**代码详解**：
- 在 `validation_results` 中反向搜索最近的 `wv_validate_script` 记录
- 将失败检查和详情作为 issue 上下文传给 LLM
- LLM 输出全量重写脚本，覆盖原文件
- 将修复记录追加到 `repair_history`（含失败的检查项和摘要）

---

#### 5. wv_validate_outline

**设计目的**：验证 `outline.md` 是否符合 `OUTLINE-FORMAT.md`。与 validate_script 模式相同。

**思路**：单独作为一个节点而非合并到 script 验证中，是为了前端时间线可以更细粒度地展示进度。

**代码详解**：与 `wv_validate_script` 结构一致，但目标文件是 `outline.md`，参考文件是 `OUTLINE-FORMAT.md`。

---

#### 6. wv_repair_outline

**设计目的**：修复 `outline.md` 或强制通过。

**代码详解**：结构与 `wv_repair_script` 相同，目标为 `outline.md`。细节日志较少，因为大纲比脚本简单。

---

#### 7. wv_checkpoint_plan_node

**设计目的**：**这是 Graph 的第一个关键中断点**。暂停工作流，让用户确认 5 件事：script、outline、主题、素材、开发模式。这是写入代码前最后也是最重要的对齐环节。

**思路**：需要给用户提供上下文来做决策，所以先扫描 `themes/` 目录列出可用主题。然后将主题列表和文件路径传给 `checkpoint_plan()` 中断函数。用户确认后提取 `selected_theme` 和 `development_mode` 写入 state。

**代码详解**：
- 扫描同级目录 `app/themes/` 下的所有 `theme.json` 文件
- 构建推荐列表（id, name, nameZh），取前 10 个
- 调用 `checkpoint_plan()` → `interrupt()` → 工作流暂停
- 用户从前端确认后，提取 `selected_theme` 和 `development_mode`
- 更新 state 供后续节点使用

---

### Phase 2 — 网页开发

目标：脚手架生成 Vite+React 项目，构建所有章节为 React 组件，逐一验证并获取用户确认。

---

#### 8. wv_scaffold_presentation

**设计目的**：从模板创建 Vite+React 演示项目。这是 Phase 2 的起点。

**思路**：使用预先写好的 `scaffold.sh` 脚本（带 `--theme` 参数非交互运行）。脚手架完成后自动启动 Vite 开发服务器，让用户能立即预览。

**代码详解**：
- 调用 `run_scaffold()` 执行脚手架脚本
- 通过 guard 确保用户已完成 checkpoint_plan 确认
- 如果脚手架成功（returncode == 0）：
  - 调用 `run_dev_server()` 后台启动 Vite
  - 设置 `presentation_url = "http://localhost:5174"`
  - 前端检测到此字段后显示"Open Presentation"链接
- 如果失败则将错误信息写入 state.errors

---

#### 9. wv_remove_example_chapter

**设计目的**：删除脚手架自带的示例章节（`01-example/`），每个真实演示从空白状态构建。

**思路**：简单的文件操作，无状态且幂等——重复执行不会造成破坏。

**代码详解**：
- 检查 `src/chapters/01-example` 是否存在
- 存在则通过 `run_shell()` 执行 `rm -rf`
- 不管是否存在都正常返回

---

#### 10. wv_build_chapter_1

**设计目的**：根据 `CHAPTER-CRAFT.md` 规则构建第 1 章（"原型章节"）。第 1 章是最重要的，它确立了整个演示的视觉风格、动画模式和组件结构。

**思路**：第 1 章需要最充分的上下文：完整的 `script.md`（口播稿）和 `outline.md`（大纲）。LLM 同时输出 `index.tsx`（组件）和 `narrations.ts`（旁白文本），通过 `===NARRATIONS===` 分隔。构建后自动更新 `chapters.ts` 注册表。

**代码详解**：
- 3 个 guard 函数确保前置条件满足（参考文件已加载、refs 已就位、不是并行模式）
- `_parse_outline_chapters()` 通过正则 `^##\s+Chapter\s+(\d+)` 解析 `outline.md`
- 构建 LLM prompt：CHAPTER-CRAFT.md + script + outline + 章节信息
- 回复用 `===NARRATIONS===` 分隔为组件文件和旁白文件
- 文件写入 `src/chapters/chapter_1/`
- `_update_chapter_registry()` 重写 `chapters.ts`，包含所有章节的 import 和注册 entry

---

#### 11. wv_validate_chapter_1

**设计目的**：根据 `CHAPTER-CRAFT.md` 自检第 1 章。与 Phase 1 验证节点模式相同。

**代码详解**：读取 `chapter_1/index.tsx`，调用 LLM 做 JSON 格式验证。其他与 validate_script 相同模式。

---

#### 12. wv_repair_chapter_1

**设计目的**：修复第 1 章的验证失败项。所有 repair 节点模式一致：读取失败检查 → LLM 重写 → 记录修复历史。

**代码详解**：同其他 repair 节点——搜索最近的 validate 结果，构建修复 prompt，重写文件，追加 repair_history。

---

#### 13. wv_checkpoint_chapter_1_node

**设计目的**：用户通过浏览器预览已完成的第 1 章，决定是批准继续还是要求修改。这是第二个主要中断点。

**代码详解**：委托给 `interrupts.checkpoint_chapter_1()`，触发 `GraphInterrupt` 暂停。中断载荷包含 `preview_url`（指向 `presentation_url?chapter=0`）供前端直接跳转到第 1 章预览。

---

#### 14. wv_select_development_mode

**设计目的**：第 1 章通过后，为后续章节设置索引。`current_chapter_index = 2`（从第 2 章开始），`total_chapters` 从 outline 解析。

**思路**：纯状态更新节点——无 LLM 调用、无 I/O。路由函数根据 `selected_mode` 分支到模式 A 或 B。

**代码详解**：
- `current_chapter_index` = 2（第 1 章已完成）
- `total_chapters` = `_parse_outline_chapters()` 的长度
- 随后 `route_development_mode()` 判断是否还有章节需要构建

---

#### 15. wv_build_chapter_n

**设计目的**：依次构建第 2～N 章。每次调用会读取前面章节的源码以保持风格一致。

**思路**：每章构建 1 次 LLM 调用。传入前面所有已构建章节的源码（每章截取前 2000 字符节省上下文窗口）。使用 `current_chapter_index` 作为指针遍历。

**代码详解**：
- 读取 `current_chapter_index` 和 `chapters` 列表
- 获取对应当前索引的章节信息
- 读取前面已构建章节的 `index.tsx`（各截取前 2000 字符）用于风格参考
- 与第 1 章相同的 `===NARRATIONS===` 解析模式
- 自动更新 `chapters.ts` 注册表

---

#### 16. wv_validate_chapter_n

**设计目的**：验证当前构建的章节 N。与第 1 章验证模式相同，但目标名动态为 `"chapter_N"`。

**代码详解**：同样 JSON 验证模式，目标文件路径随 `current_chapter_index` 动态计算。

---

#### 17. wv_repair_chapter_n

**设计目的**：修复章节 N 的验证失败项。同其他 repair 节点模式。目标名 `"chapter_N"` 用于修复计数。

**代码详解**：与其他 repair 节点结构完全一致。

---

#### 18. wv_increment_chapter_index

**设计目的**：章节索引 +1。是 Phase 2 循环的步进器。

**思路**：最轻量的节点——纯 state 更新 `current_chapter_index: +1`。路由函数随后判断是否超过总章节数来决定继续循环还是结束。

**代码详解**：`return {"current_chapter_index": state.get("current_chapter_index", 2) + 1}`

---

#### 19. wv_checkpoint_chapter_n_node

**设计目的**：仅在模式 A 中使用。每章构建后暂停，让用户预览并决定继续还是退出。

**思路**：用户的 `"continue"` 字段和 `current_chapter_index <= total_chapters` 共同决定路由方向。

**代码详解**：委托给 `interrupts.checkpoint_chapter_n()`，传入当前章节索引。中断载荷包含 `preview_url` 指向该章节（`?chapter=N-1`）。

---

#### 20. wv_checkpoint_remaining_batch_node

**设计目的**：仅在模式 B 中使用。所有剩余章节构建完成后，一次性展示所有章节供用户确认。

**代码详解**：委托给 `interrupts.checkpoint_remaining_batch()`，传入已构建章节索引范围。中断载荷包含 `preview_url` 指向第一批章节。

---

#### 21. wv_transition_to_phase3

**设计目的**：Phase 2 → Phase 3 的转换节点。验证所有合同约定的 Phase 2 产物是否存在，然后将 phase 推进到 phase3。

**思路**：`check_artifact_contract()` 检查所有应该生成的文件是否都在。即使缺失也不阻塞（音频阶段可选），仅记录 error。phase 始终推进到 phase3。

**代码详解**：
- 调用 `check_artifact_contract(state, phase=2)` 获取缺失文件列表
- 有缺失则追加到 `errors`
- 设置 `current_phase = "phase3"`

---

### Phase 3 — 音频合成

目标：可选地为每段旁白合成 AI 语音。用户在中断点选择 yes/no，yes 则走完整 TTS 管线。

---

#### 22. wv_checkpoint_audio_node

**设计目的**：询问用户是否需要 AI 配音。将用户的 `synthesize_audio` 选择写入 state，供路由函数决策。

**代码详解**：委托给 `interrupts.checkpoint_audio()`，从用户确认中提取 `choice`。

---

#### 23. wv_extract_narrations

**设计目的**：扫描所有章节的 `narrations.ts`，生成统一的 `audio-segments.json` 清单。每段旁白附带预估时长供 TTS 使用。

**代码详解**：通过 `run_npm()` 运行 `npm run extract-narrations`。失败时不阻塞流程，仅记录错误。

---

#### 24. wv_checkpoint_audio_segments_node

**设计目的**：在调用付费 TTS API 之前让用户审查音频段。用户可以验证文本是否正确、段落切分是否合理。

**代码详解**：委托给 `interrupts.checkpoint_audio_segments()`，触发中断展示 `audio-segments.json` 路径给用户。

---

#### 25. wv_synthesize_audio

**设计目的**：调用 TTS 服务商（Minimax/OpenAI）为每段生成音频文件。这是整个流程中成本最高的步骤。

**代码详解**：通过 `run_npm()` 运行 `npm run synthesize-audio`。失败时不阻塞。

---

#### 26. wv_report_audio_anomalies

**设计目的**：合成后的质量检查。扫描 `audio-segments.json` 检查可疑条目（如空时长但有文本的段）。仅报告，不阻断。

**思路**：Phase 始终推进到 phase4，即使发现异常。异常信息放入 `state.errors` 供前端展示。

**代码详解**：
- 读取 `audio-segments.json`，遍历 segments
- 检查 `estimated_duration_seconds == 0` 且文本非空的段
- 异常文字追加到 errors 列表（最多 5 条）
- 设置 `current_phase = "phase4"`

---

### Phase 4 — 录屏指导

#### 27. wv_recording_guidance

**设计目的**：终点节点。设置 `final_summary` 包含工作区路径、主题和录屏说明。前端检测到 `final_summary` 后渲染"工作流完成"页面。

**思路**：纯状态更新。构建一个多行字符串包含操作步骤。`final_summary` 是整个 Graph 完成的哨兵值。

**代码详解**：`return {"final_summary": "Presentation complete!\nWorkspace: ...\nTheme: ...\n\nTo record:\n1. cd ...\n2. npm run dev\n3. ?auto=1\n4. Screen record"}`

---

## 路由函数

每个路由函数读取 state 并返回下一个节点名称。纯确定性函数（无 LLM、无 I/O）。共 8 个：

| 路由函数 | 逻辑 |
|---|---|
| `route_script_validation` | script 通过？→ outline / 失败？→ repair / 耗尽？→ 强制通过 |
| `route_outline_validation` | outline 通过？→ checkpoint_plan / 失败？→ repair |
| `route_chapter_1_validation` | ch1 通过？→ checkpoint / 失败？→ repair |
| `route_development_mode` | 还有章节？→ build_chapter_n / 完成？→ check_storage |
| `route_chapter_n_validation` | 通过？→ 下一步 / 失败？→ repair。模式 A → checkpoint，B → 继续或批量 |
| `route_mode_a_checkpoint` | 继续且还有章节？→ 循环 / 完成？→ check_storage |
| `route_chapter_loop_continue` | index ≤ total？→ 继续构建 / 完成？→ check_storage |
| `route_audio_decision` | 合成？→ extract / 跳过？→ recording_guidance |

---

## 辅助函数

| 函数 | 用途 |
|---|---|
| `_parse_outline_chapters()` | 正则解析 `outline.md` → `[{id, title}]` |
| `_get_repair_count()` | 统计 `repair_history` 中某个目标的修复次数 |
| `_update_chapter_registry()` | 重写 `chapters.ts`：生成 import 语句和注册表 |
| `_think()` | 追加 `{type, content, ts}` 到 thinking_log |
| `_wrap_node()` | 包装器：自动追踪 completed_nodes、thinking_log、计时 |
| `_last_validation_passed()` | 按节点名查找最近一次验证结果 |

---

## Graph 构建和编译

`build_web_video_graph()` 是唯一的导出工厂函数：

1. 创建 `StateGraph(VideoWorkflowState)`
2. 注册 22 个节点（每个用 `_wrap_node()` 包装）
3. 连接边和条件边
4. 使用 `MemorySaver()` checkpointer 编译（支持中断/resume）

```python
def build_web_video_graph() -> StateGraph:
    builder = StateGraph(VideoWorkflowState)
    # ... 注册节点和边 ...
    return builder.compile(checkpointer=MemorySaver())
```

`MemorySaver` 是 LangGraph 的内存级检查点实现，使 `Command(resume=...)` 和 `interrupt()` 机制正常工作。生产环境应替换为数据库持久化。
