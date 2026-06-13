# 前端测试指南

## 启动环境

打开两个终端：

```bash
# 终端 1: 启动后端 API（需要在 ezto-agent/ 目录下）
cd ezto-agent/
cp .env.example .env   # 首次使用，然后编辑 .env 填入 DEEPSEEK_API_KEY
python -m uvicorn app.api.server:app --reload --port 8001

# 终端 2: 启动前端 dev server（需要在 frontend/ 目录下）
cd ezto-agent/frontend/
npm run dev
```

前端默认运行在 `http://localhost:5173`，Vite 自动将 `/api` 请求代理到后端 `http://localhost:8001`。

## 工作流测试步骤

### Phase 1 — 内容编写

1. 打开 `http://localhost:5173`，点击"创建新项目"
2. 选择输入类型（原始文章 / 口播稿），粘贴内容，点击"开始制作"
3. 前端自动轮询状态，展示当前节点。正常流程：
   ```
   wv_identify_input → wv_prepare_source_files → wv_validate_script → (可能 repair) → wv_validate_outline → (可能 repair)
   ```
4. 到达 **Checkpoint Plan** 中断时，页面展示 5 件事确认界面：
   - 稿子 (script.md) — 确认或提修改意见
   - 开发计划 (outline.md) — 确认或提修改意见
   - 选择主题 — 从 23 个主题中选择
   - 素材准备 — 三个 radio 选项
   - 开发模式 — A: 逐章确认 / B: 顺序开批量验收 / C: 并行开发
5. 选择完成后点击"确认并继续"

### Phase 2 — 网页开发

1. 后端执行：`wv_scaffold_presentation`（脚手架）+ `wv_remove_example_chapter`（删 demo）
2. `wv_build_chapter_1` — LLM 生成第 1 章 React 组件（较慢，需等待 10-30s）
3. `wv_validate_chapter_1` — LLM 自检
4. 验证失败会自动进入 `wv_repair_chapter_1`，修复后重新验证。最多重试 3 次
5. 到达 **第 1 章验收** 中断，页面展示验收清单（5 项）：
   - 勾选验收项
   - 不通过时填写修改反馈
6. 确认后进入模式选择/章节循环

#### 模式 A（默认）

```
build_chapter_n → validate → (可能 repair) → checkpoint_chapter_n [中断] → increment → 循环
```

每章完成后页面弹出验收界面。选择"继续"进入下一章，"停止"跳到 `transition_to_phase3`。

#### 模式 B

```
build_chapter_n → validate → (可能 repair) → increment → 循环全部完成 → checkpoint_remaining_batch [中断]
```

所有章完成后一次性弹出批量验收界面。

### Phase 2 完成 → Phase 3

`transition_to_phase3` 节点验证 artifact 契约，完成后进入 Phase 3。

### Phase 3 — 音频合成（可选）

1. **Checkpoint Audio** 中断：选择"合成音频"或"跳过"
2. 选择合成则执行：
   - `wv_extract_narrations` — 扫描所有章节 narrations → 生成 `audio-segments.json`
   - `wv_checkpoint_audio_segments` 中断 — 确认分段正确
   - `wv_synthesize_audio` — 调 TTS 合成每步 mp3
   - `wv_report_audio_anomalies` — 检查零时长段等异常

### Phase 4 — 完成

`wv_recording_guidance` 输出录屏指引，页面展示最终 summary。

## 调试技巧

### 查看当前状态

```bash
curl http://localhost:8001/api/workflow/{thread_id}
```

返回当前 `current_node`、`pending_interrupt`、`errors` 等。

### 手动恢复中断（不用前端）

```bash
curl -X POST http://localhost:8001/api/workflow/{thread_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"confirmations": {"selected_theme": "midnight-press", "development_mode": "A"}}'
```

### SSE 事件流

```bash
curl -N http://localhost:8001/api/workflow/{thread_id}/events
```

以 SSE 格式实时输出节点变化。

### 查看工作区文件

```bash
# 列出所有 artifact
curl http://localhost:8001/api/workflow/{thread_id}/artifacts

# 读取文件内容
curl http://localhost:8001/api/workflow/{thread_id}/artifact/script.md
```

## 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| 提交后一直显示"正在执行" | LLM 调用较慢（10-30s 正常） | 等待，可查看 SSE 事件流确认 |
| 前端白屏 / 无法连接 | 后端未启动或端口不对 | 确认 `uvicorn` 运行在 8001 端口 |
| `DEEPSEEK_API_KEY not configured` | `.env` 文件未配置 | 复制 `.env.example` 为 `.env` 并填入 key |
| 主题列表为空 | 主题目录路径问题 | 确认 `app/themes/` 下有 23 个主题目录 |
| 脚手架失败 | Windows 缺少 bash | 需安装 Git Bash 或 WSL |
| checkpoint 提交后无响应 | resume 请求的 key 不匹配 | 对照 `interrupts.py` 中 `interrupt()` 的 payload 确认字段名 |
