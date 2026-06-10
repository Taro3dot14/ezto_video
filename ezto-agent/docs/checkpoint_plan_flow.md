# Checkpoint Plan 完整数据流详解

本文档以 `wv_checkpoint_plan_node` 为例，完整追踪一次 Interrupt 从前端到后端再返回的全路径。

---

## 一句话总结

`interrupt()` 是 LangGraph 提供的**暂停+等待用户输入**机制。当节点调用 `interrupt(payload)` 时：
1. Graph 执行立即暂停，`payload` 保存到 state（前端通过 SSE 或 GET 接口看到）
2. 用户在前端操作，点击"确认"
3. 前端 POST `/api/{thread_id}/resume` 把用户输入发回
4. LangGraph 让 `interrupt()` 函数返回用户输入值，节点继续执行

---

## 完整执行路线图

```
┌─────────────────────────────────────────────────────────────────────────┐
│  后端 Graph 执行线程                                                      │
│                                                                          │
│  wv_checkpoint_plan_node()                                               │
│    → checkpoint_plan()                                                   │
│      → _store_and_interrupt(payload)                                     │
│        → interrupt(payload)  ──┬── [首次] GraphInterrupt 异常 ──→ 暂停   │
│                                │                                         │
│                                └── [恢复] 直接返回用户输入值 ──→ 继续     │
└─────────────────────────────────────────────────────────────────────────┘
                                                                           
                           ｜暂停了                                        
                           ▼                                                
┌─────────────────────────────────────────────────────────────────────────┐
│  workflow_manager._run_graph()     (astream 循环结束)                     │
│    → pop_last_interrupt_payload()  (取出之前存的 payload)                 │
│    → state["pending_interrupt"] = payload  (挂到 state 上)               │
└─────────────────────────────────────────────────────────────────────────┘
                                                                           
                           ｜                                              
                           ▼                                                
┌─────────────────────────────────────────────────────────────────────────┐
│  routes.py  /api/{thread_id}/events    (SSE 轮询)                       │
│    → 检测到 pending_interrupt 变化                                       │
│    → 推送 state_change 事件给前端                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                                                           
                           ｜                                              
                           ▼                                                
┌─────────────────────────────────────────────────────────────────────────┐
│  前端 WorkflowPage.tsx              (EventSource onmessage)             │
│    → fetchState() → GET /api/{thread_id}                                │
│    → 发现 state.pending_interrupt.type === "checkpoint_plan"            │
│    → 渲染 <CheckpointPlanView />                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                                                           
                           ｜用户操作                             
                           ▼                                                
┌─────────────────────────────────────────────────────────────────────────┐
│  用户选择主题、开发模式 → 点击"确认并继续"                                  │
│                                                                          │
│  CheckpointPlanView.handleConfirm()                                      │
│    → onResume({ selected_theme, development_mode, ... })                 │
│                                                                          │
│  WorkflowPage.tsx.handleResume()                                         │
│    → POST /api/{thread_id}/resume                                        │
│      body: { confirmations: { selected_theme, development_mode, ... } }  │
└─────────────────────────────────────────────────────────────────────────┘
                                                                           
                           ｜                                              
                           ▼                                                
┌─────────────────────────────────────────────────────────────────────────┐
│  routes.py  POST /api/{thread_id}/resume                                │
│    → mgr.resume_workflow(thread_id, confirmations)                       │
│                                                                          │
│  workflow_manager.resume_workflow()                                      │
│    → pending_interrupt = None  (清除，前端切回 loading)                   │
│    → asyncio.create_task(_run_resume())                                  │
│                                                                          │
│  workflow_manager._run_resume()                                          │
│    → graph.astream(Command(resume=confirmations), config)                │
│                                                                          │
│  LangGraph 把 confirmations 当作 interrupt() 的返回值                     │
└─────────────────────────────────────────────────────────────────────────┘
                                                                           
                           ｜                                              
                           ▼                                                
┌─────────────────────────────────────────────────────────────────────────┐
│  checkpoint_plan() 收到 response = {selected_theme, ...}                │
│    → _ensure_confirmations() → {"user_confirmations": {"checkpoint_plan": response}}  │
│                                                                          │
│  wv_checkpoint_plan_node() 继续执行                                       │
│    → 提取 selected_theme → state["selected_theme"]                       │
│    → 提取 development_mode → state["selected_mode"]                      │
│    → 返回 {selected_theme, selected_mode, user_confirmations, ...}       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 详细步骤分解

### Step 1: 节点函数调用 checkpoint_plan()

文件：`app/graph/web_video.py:264`

```python
def wv_checkpoint_plan_node(state: VideoWorkflowState) -> dict:
    # 扫描 themes/ 目录，构建主题推荐列表
    themes_dir = Path(__file__).parent.parent / "themes"
    recommendations = []
    if themes_dir.exists():
        for td in sorted(themes_dir.iterdir()):
            if not td.is_dir(): continue
            meta_file = td / "theme.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                recommendations.append({
                    "id": meta.get("id", td.name),
                    "name": meta.get("name", ""),
                    "nameZh": meta.get("nameZh", ""),
                })

    # 调用 checkpoint_plan() —— 这是中断发生的地方
    result = checkpoint_plan(state, recommendations[:10], ["script.md", "outline.md"])

    # 这行代码在**恢复后**才会执行到
    response = result.get("user_confirmations", {}).get("checkpoint_plan", {})
    if isinstance(response, dict):
        theme = response.get("selected_theme")
        if theme:
            result["selected_theme"] = theme   # 写入 state
        mode = response.get("development_mode")
        if mode:
            result["selected_mode"] = mode      # 写入 state
    return result
```

**关键理解**：`checkpoint_plan()` 调用后函数不会立即返回——它会触发 `interrupt()` 导致 Graph 暂停。再次恢复时，`interrupt()` 返回用户输入值，函数继续执行完成剩余逻辑。

---

### Step 2: _store_and_interrupt() 保存载荷并中断

文件：`app/runtime/interrupts.py:28`

```python
_LAST_INTERRUPT_PAYLOAD: dict | None = None  # 模块级全局变量

def _store_and_interrupt(payload: dict) -> Any:
    global _LAST_INTERRUPT_PAYLOAD
    _LAST_INTERRUPT_PAYLOAD = payload          # ① 把 payload 存到全局变量
    try:
        result = interrupt(payload)            # ② 调用 LangGraph 的 interrupt()
        # 恢复路径：interrupt() 返回了用户输入值
        _LAST_INTERRUPT_PAYLOAD = None         # ③ 清除，防止误判
        return result                          # ④ 返回用户输入
    except GraphInterrupt:
        # 首次路径：interrupt() 抛出了异常
        raise  # payload 保留在全局变量中供后续读取
```

**这就是中断的核心机制**。关键点：
- 首次执行 `interrupt()` 抛出 `GraphInterrupt`，函数不会返回
- `_LAST_INTERRUPT_PAYLOAD` 保留在模块变量中，供 `pop_last_interrupt_payload()` 读取
- 恢复后 `interrupt()` 直接返回用户输入，不再抛异常

---

### Step 3: GraphInterrupt 传播 — astream 循环停止

文件：`app/graph/web_video.py:800 (_wrap_node)`

```python
def _wrap_node(name: str, fn):
    def wrapped(state: VideoWorkflowState) -> dict:
        try:
            node_result = fn(state)   # 执行节点函数
            # ... 正常路径 ...
        except Exception as e:
            if isinstance(e, GraphInterrupt):
                logger.info("⏸ %s interrupted", name)
                raise                 # 重新抛出，不处理
            # ... 其他异常 ...
            raise
```

文件：`app/api/workflow_manager.py:126 (_run_graph)`

```python
async def _run_graph(self, thread_id, state, config):
    try:
        async for output in self._graph.astream(state, config, stream_mode="values"):
            self._threads[thread_id]["state"] = output
        # 循环**正常**结束了（interrupt 不抛异常到外面，只是停止迭代）
        
        # 检查是否有中断
        payload = pop_last_interrupt_payload()
        if payload:
            self._threads[thread_id]["state"]["pending_interrupt"] = payload
            return
    except Exception as e:
        # ... 错误处理 ...
```

当一个节点内 `interrupt()` 抛出 `GraphInterrupt` 时：
1. `_wrap_node` 的 `except` 捕获到 `GraphInterrupt`，**重新抛出**
2. LangGraph 运行时捕获这个异常，**正常结束 astream 迭代**（不是异常退出！）
3. `async for` 循环结束，进入后面的代码
4. `pop_last_interrupt_payload()` 从模块变量中取出之前存储的 payload
5. 把 payload 写入 state 的 `pending_interrupt` 字段

---

### Step 4: SSE 推送 — 前端检测到中断

文件：`app/api/routes.py:146`

```python
async def event_generator():
    last_pending_interrupt = None
    while True:
        state = mgr.get_state(thread_id)
        current_pi = state.get("pending_interrupt")
        
        # 检测 pending_interrupt 是否有变化
        pi_changed = current_pi and current_pi != last_pending_interrupt
        
        if pi_changed:
            last_pending_interrupt = current_pi
            event = {
                "type": "state_change",
                "current_node": state.get("current_node"),
                "pending_interrupt": state.get("pending_interrupt"),
            }
            yield f"data: {json.dumps(event)}\n\n"   # 推送给前端
        
        if state.get("final_summary"):
            break
        
        await asyncio.sleep(1)  # 每秒轮询
```

SSE 端点每秒轮询 state，当 `pending_interrupt` 从 `None` 变成有值时，向前端推送 `state_change` 事件。

---

### Step 5: 前端渲染 CheckpointPlanView

文件：`frontend/src/pages/WorkflowPage.tsx:99`

```tsx
// state.pending_interrupt 有值了:
//   { type: "checkpoint_plan", files: {...}, theme_recommendations: [...], ... }

const interrupt = state.pending_interrupt;
const interruptType = interrupt?.type;

// 根据 type 渲染不同的 checkpoint 组件
{interruptType === "checkpoint_plan" && (
  <CheckpointPlanView
    interrupt={interrupt!}
    threadId={threadId!}
    onResume={handleResume}    // ← 用户点击确认时调用的函数
  />
)}
```

文件：`frontend/src/components/CheckpointPlanView.tsx:32`

```tsx
const handleConfirm = () => {
  onResume({
    script_feedback: null,
    outline_feedback: null,
    selected_theme: selectedTheme || themes[0]?.id || "midnight-press",
    material_plan: materialPlan,
    development_mode: devMode,
  });
  // ↑ 这 5 个字段就是用户输入，会被发送回后端
};
```

用户点击"确认并继续"后，`onResume()` 被调用，传入包含 5 个字段的对象。

---

### Step 6: 前端调用 resume API

文件：`frontend/src/pages/WorkflowPage.tsx:64`

```tsx
const handleResume = async (confirmations: Record<string, unknown>) => {
  if (!threadId) return;
  setError(null);
  try {
    const res = await resumeWorkflow(threadId, confirmations);
    setState(res.state);  // 更新 state（此时 pending_interrupt = None）
  } catch (e) {
    setError(e instanceof Error ? e.message : "提交确认失败");
  }
};
```

文件：`frontend/src/api/client.ts:66`

```typescript
export async function resumeWorkflow(
  threadId: string,
  confirmations: Record<string, unknown>,
): Promise<{ thread_id: string; state: WorkflowState }> {
  return request(`/workflow/${threadId}/resume`, {
    method: "POST",
    body: JSON.stringify({ confirmations }),  // ← 用户输入放这里
  });
}
```

---

### Step 7: 后端 resume 端点

文件：`app/api/routes.py:98`

```python
@router.post("/workflow/{thread_id}/resume")
async def resume_workflow(thread_id: str, req: ResumeRequest):
    state = await mgr.resume_workflow(thread_id, req.confirmations)
    return ResumeWorkflowResponse(thread_id=thread_id, state=_state_to_response(state))
```

文件：`app/api/workflow_manager.py:158`

```python
async def resume_workflow(self, thread_id, confirmations):
    # 1) 立即清除 pending_interrupt，前端从"中断界面"变"加载中"
    thread["state"]["pending_interrupt"] = None
    
    # 2) 后台启动恢复任务
    asyncio.create_task(self._run_resume(thread_id, config, confirmations, t0))
    
    # 3) 直接返回已清除的 state（恢复在后台异步执行）
    return thread["state"]
```

---

### Step 8: _run_resume — Command(resume=...) 恢复 Graph

文件：`app/api/workflow_manager.py:194`

```python
async def _run_resume(self, thread_id, config, confirmations, t0):
    # 清除 stale pending_interrupt（双重保险）
    current = self._threads.get(thread_id, {}).get("state")
    if current:
        current["pending_interrupt"] = None
    
    try:
        # ★ 关键：Command(resume=confirmations)
        # LangGraph 把 confirmations 传给之前中断的 interrupt() 调用
        async for output in self._graph.astream(
            Command(resume=confirmations), config, stream_mode="values",
        ):
            self._threads[thread_id]["state"] = output
```

**`Command(resume=confirmations)`** 是 LangGraph 的 resume 机制：
- 告诉 LangGraph："之前 interrupt() 暂停的地方，现在用 `confirmations` 作为返回值继续"
- 系统定位到之前暂停的节点，让 `interrupt()` 返回 `confirmations`

---

### Step 9: checkpoint_plan() 收到用户输入

回到 `_store_and_interrupt()`：

```python
def _store_and_interrupt(payload: dict) -> Any:
    global _LAST_INTERRUPT_PAYLOAD
    _LAST_INTERRUPT_PAYLOAD = payload
    try:
        result = interrupt(payload)
        # 恢复路径：这次 interrupt() 没有抛异常，直接返回了！
        _LAST_INTERRUPT_PAYLOAD = None          # 清除 payload
        return result  # result = {selected_theme, development_mode, ...}
    except GraphInterrupt:
        raise
```

然后 `checkpoint_plan()` 拿到 `result`：

```python
def checkpoint_plan(state, theme_recommendations, material_list):
    response = _store_and_interrupt({...})   # ← 现在 response 是用户输入
    return _ensure_confirmations(response, "checkpoint_plan")
    # → {"user_confirmations": {"checkpoint_plan": response}}
```

最后回到 `wv_checkpoint_plan_node()`：

```python
def wv_checkpoint_plan_node(state):
    result = checkpoint_plan(state, recommendations[:10], ["script.md", "outline.md"])
    # 这些代码**现在**才执行到
    response = result.get("user_confirmations", {}).get("checkpoint_plan", {})
    if isinstance(response, dict):
        theme = response.get("selected_theme")
        if theme:
            result["selected_theme"] = theme  # state.selected_theme = "midnight-press"
        mode = response.get("development_mode")
        if mode:
            result["selected_mode"] = mode    # state.selected_mode = "A"
    return result  # → LangGraph 将返回值合并到 state 中
```

---

## 完整文件路径索引

| 步骤 | 文件 | 关键函数/组件 |
|---|---|---|
| 节点调用 | `app/graph/web_video.py:264` | `wv_checkpoint_plan_node()` |
| 中断函数 | `app/runtime/interrupts.py:28` | `_store_and_interrupt()` |
| 中断原语 | `langgraph.types.interrupt()` | `interrupt()` |
| Payload 读取 | `app/runtime/interrupts.py:20` | `pop_last_interrupt_payload()` |
| Graph 调度 | `app/api/workflow_manager.py:116` | `_run_graph()` |
| SSE 推送 | `app/api/routes.py:146` | `event_generator()` |
| 前端页面 | `frontend/src/pages/WorkflowPage.tsx` | 事件处理 + 条件渲染 |
| Checkpoint UI | `frontend/src/components/CheckpointPlanView.tsx` | 5 件事的 UI 表单 |
| API 客户端 | `frontend/src/api/client.ts:66` | `resumeWorkflow()` |
| Resume 端点 | `app/api/routes.py:98` | `resume_workflow()` |
| Resume 调度 | `app/api/workflow_manager.py:158` | `resume_workflow()` + `_run_resume()` |
| 恢复执行 | `app/api/workflow_manager.py:194` | `Command(resume=confirmations)` |

---

## 关键设计要点

1. **`_LAST_INTERRUPT_PAYLOAD` 全局变量的必要性**：`interrupt()` 抛出异常时无法返回值，所以必须先存到全局变量，异常后再读取。

2. **`Command(resume=...)` 是恢复的唯一方式**：不能直接再次调用节点函数，必须通过 LangGraph 的 resume 机制让 `interrupt()` 返回。

3. **`pending_interrupt = None` 的清除时机**：必须在 resume 请求到达时立即清除，而不是等后台恢复任务完成——否则前端会一直卡在中断界面。

4. **`_store_and_interrupt()` 的双重行为**：
   - 首次：存 payload → `interrupt()` 抛异常 → payload 留在全局
   - 恢复：`interrupt()` 正常返回 → 清除 payload → 返回用户输入

5. **后端 resume 是异步的**：`resume_workflow()` 启动后台任务后立即返回清除后的 state，恢复的 Graph 通过 SSE 流式推送后续的 state 变化。
