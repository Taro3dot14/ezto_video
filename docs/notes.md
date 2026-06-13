# 个人复盘笔记

## LLM 客户端设计：全局单例 vs 常规实例化

### 常规做法（以 OpenAI SDK 为例）

```python
from openai import OpenAI

client = OpenAI(api_key="sk-xxx")  # 显式实例化

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hi"}],
)
```

### 本项目做法

```python
from app.core import llm

response = llm.chat(user="Hi")  # 直接调用，无需实例化
```

### 核心区别

| 维度 | 常规 SDK 实例化 | 本项目全局单例 |
|---|---|---|
| **实例化方式** | 使用者手动 `new`，传入配置 | 模块级函数，隐式从 `Settings` 读取配置 |
| **配置绑定** | 调用方自己管理 API key | 统一由 `.env` / 环境变量管理 |
| **消息构建** | 调用方构建完整 `messages` 列表 | 提供 `system` / `user` 快捷参数，内部组装 |
| **接口简洁度** | 完整但繁琐 | 精简，只暴露项目需要的操作 |
| **灵活性** | 一个进程可创建多个 client（不同模型、不同 key） | 全局只有一个配置（但单次调用可 override） |
| **可测试性** | 构造函数注入 mock，天然可测试 | 需要 `patch` 模块级函数（也可以但更绕） |
| **依赖** | 需要装 `openai` SDK | 只用已有的 `httpx`，零新增依赖 |
| **类型安全** | SDK 提供完整的 Pydantic 响应模型 | 手动解析 JSON，只有 `str` 返回 |
| **高级特性** | 原生 function calling、structured output、assistant API | 不做（项目不需要） |
| **重试策略** | SDK 内置（需配置） | 手动实现指数退避 |

### 为什么本项目选全局单例

1. **项目内只用一家 LLM（DeepSeek）**，没有多 provider 混用的需求
2. **配置集中管理**：API key 只在一个地方配（`.env`），所有节点自动读到
3. **调用极简**：图节点只需要 `llm.chat(system=..., user=...)` 一行，不需要关心客户端生命周期
4. **零新增依赖**：`httpx` 已被 `langsmith` 引入，不必多装一个 `openai` 包

### 什么场景应该用常规做法

- 需要同时调用多家 LLM（如 DeepSeek 写稿 + OpenAI 做 embedding）
- 需要 mock 客户端做单元测试
- 需要 SDK 的高级特性（tool calling、structured output）
- 每个请求需要不同的配置（临时换模型、换 key）

### 两者不冲突

可以把全局单例看作"快捷方式"，底层仍可实例化 SDK 客户端处理复杂场景：

```python
from app.core import llm, settings

# 简单场景用快捷方式
reply = llm.chat(user="Hi")

# 复杂场景自己实例化 SDK
client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
```
