# deepagent

openclound 的 **deep agent 基础包**,封装 [LangChain `deepagents`](https://github.com/langchain-ai/deepagents),
集成 **litellm 网关 / MCP / skills / 长短期记忆 / 安全中间件**,并附带一个
**类 Claude Code 的交互式 CLI**。

## 能力一览

| 能力 | 说明 |
|---|---|
| 任务规划 | 内置 `write_todos`,自动维护任务清单 |
| 文件系统 | `ls` / `read_file` / `write_file` / `edit_file` / `glob` / `grep`(真实磁盘,根目录=工作区) |
| Shell | `execute` 工具,**跨平台**(Windows `cmd` / POSIX `/bin/sh`),可关 |
| 子代理 | `task` 工具,隔离上下文执行子任务 |
| MCP | 经 `langchain-mcp-adapters` 挂载任意 MCP server 工具 |
| Skills | 工作区 `skills/` 下每个含 `SKILL.md` 的目录,按需加载 |
| 记忆 | `memories/AGENTS.md` 注入系统提示 + 短期(checkpointer)/ 长期(store) |
| 健壮性 | 模型 / 工具自动重试、调用上限、备用模型回退 |
| 上下文管理 | 过旧工具输出自动清理(`ContextEditingMiddleware`) |
| 安全 | 可选 PII 脱敏、HITL(高危工具人工确认) |
| CLI | token 级流式输出、工具可视化、多轮会话、审批提示 |

模型经 **litellm 网关**(OpenAI 兼容)接入,默认指向
`https://aigateway-sandbox.mspbots.ai/v1`,用 `ChatOpenAI` 对接,因此无需直连
各家厂商 SDK,换模型只改一个环境变量。

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)(包 / 环境管理)
- 环境变量 `OPENAI_API_KEY`(模型端点密钥;连接走标准 OpenAI 变量)

## 目录结构

```
packages/deepagent/
├── pyproject.toml          # uv_build(src 布局) + ruff/mypy/pytest + deepagent CLI 入口
├── aegra.json              # Aegra 部署配置:注册图 deepagent -> graph.py:graph
├── .env.example            # 配置模板(AGENT_* + Aegra 部署变量)
├── README.md
├── src/
│   └── deepagent/
│       ├── __init__.py     # 公共 API 导出
│       ├── config.py       # Settings(pydantic-settings)+ get_settings(读 OPENAI_*/AGENT_*/.env)
│       ├── model.py        # build_model():经 OpenAI 兼容端点接入 ChatOpenAI
│       ├── mcp.py          # load_mcp_tools():加载 MCP server 工具
│       ├── middleware.py   # build_middleware() / interrupts()
│       ├── workspace.py    # init_workspace():首次从 _data 模板初始化工作区
│       ├── agent.py        # build_agent() / build_async_agent() 入口
│       ├── graph.py        # Aegra 图工厂 graph()(platform_managed=True)
│       ├── cli.py          # 交互式 REPL(deepagent 命令)
│       ├── _data/          # 随包模板:skills/ 与 memories/AGENTS.md
│       └── py.typed
└── tests/
    └── test_smoke.py
```

## 安装 / 开发

```bash
# 在包目录内(或从仓库根加 --directory packages/deepagent)
uv sync                 # 创建 .venv 并安装依赖(含 dev 组)
uv run pytest           # 运行测试
uv run ruff check .     # lint
uv run ruff format .    # 格式化
uv run mypy src         # 类型检查
```

## 用法

### 1. 作为库

```python
import os
from deepagent import build_agent

os.environ["OPENAI_API_KEY"] = "..."   # 模型端点密钥(默认走内置网关)

agent = build_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "调研 LangGraph 并总结"}]})
print(result["messages"][-1].content)
```

自定义工具与子代理:

```python
from langchain_core.tools import tool

@tool
def search(query: str) -> str:
    """A simple search tool."""
    return f"results for {query}"

agent = build_agent(
    tools=[search],
    subagents=[{
        "name": "researcher",
        "description": "用于深入调研子问题",
        "system_prompt": "你是严谨的研究员。",
    }],
)
```

### 2. 挂载 MCP 工具(异步)

```python
import asyncio
from deepagent import build_async_agent

async def main():
    agent = await build_async_agent(mcp_servers={
        "fs": {"transport": "stdio", "command": "python", "args": ["server.py"]},
        "weather": {"transport": "streamable_http", "url": "http://localhost:8000/mcp"},
    })
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "..."}]})
    print(result["messages"][-1].content)

asyncio.run(main())
```

### 3. 交互式 CLI(类 Claude Code)

```bash
deepagent                      # 进入交互式 REPL(token 级流式输出)
deepagent "重构 foo.py"         # 单次任务后退出
deepagent --hitl               # 高危工具(写文件 / shell)执行前人工确认
deepagent --mcp servers.json   # 额外挂载 MCP 工具
deepagent --no-shell           # 禁用 shell 工具
```

REPL 内命令:`/exit` 退出 · `/reset` 开新会话 · `/help` 帮助。

## 配置(环境变量 / .env)

推荐用 `.env`:复制模板后填入网关密钥即可(`.env` 已被 `.gitignore` 忽略):

```bash
cp .env.example .env        # 然后编辑 .env,至少填 OPENAI_API_KEY
```

`get_settings()` 启动时会自动加载**当前工作目录**下的 `.env`。优先级:
**shell 环境变量 / CLI 参数 > `.env` > 代码默认值**。各项均有合理默认值:

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | 内置网关 | OpenAI 兼容 `/v1` 端点(留空用默认网关;可指向 MiniMax 等) |
| `OPENAI_API_KEY` | `anything` | 端点密钥 |
| `AGENT_MODEL` | `claude-sonnet-4-6` | 模型名(由网关路由) |
| `AGENT_TEMPERATURE` | `0.0` | 采样温度 |
| `AGENT_FALLBACK_MODEL` | 空 | 主模型失败时的备用模型 |
| `AGENT_WORKSPACE` | `.agent` | 工作区目录(agent 的文件系统根) |
| `AGENT_ENABLE_SHELL` | `1` | 是否启用 `shell` 工具 |
| `AGENT_ENABLE_FILE_SEARCH` | `0` | 是否启用 ripgrep 文件搜索(deepagents 已有 glob/grep) |
| `AGENT_ENABLE_HITL` | `0` | 高危工具是否需人工确认 |
| `AGENT_PII_STRATEGY` | `off` | PII 脱敏策略:`off`/`block`/`redact`/`mask`/`hash` |
| `AGENT_MODEL_CALL_LIMIT` | 空 | 单次运行模型调用上限 |
| `AGENT_TOOL_CALL_LIMIT` | 空 | 单次运行工具调用上限 |
| `AGENT_MODEL_MAX_RETRIES` | `2` | 模型调用最大重试 |
| `AGENT_TOOL_MAX_RETRIES` | `2` | 工具调用最大重试 |
| `AGENT_CONTEXT_EDIT_TRIGGER_TOKENS` | `100000` | 触发清理旧工具输出的 token 阈值 |

## 工作区与 skills / memory

首次运行时,`init_workspace()` 会把随包模板(`_data/`)中的 `skills/` 与
`memories/AGENTS.md` 复制到工作区(默认 `./.agent/`)。之后:

- 把领域工作流写成 `skills/<名字>/SKILL.md`(YAML frontmatter + Markdown),
  agent 会按需加载。
- 在 `memories/AGENTS.md` 写团队 / 项目准则,会注入系统提示。
- 直接编辑工作区内文件即可,模板只在缺失时初始化,不覆盖你的修改。

## Aegra 部署(生产持久化 / Agent Protocol)

本包已是一个 **[Aegra](https://docs.aegra.dev) 项目**——Aegra 是 LangGraph Platform
的自托管开源替代(FastAPI + PostgreSQL)。它在运行时用 **Postgres 自动接管持久化**
(checkpointer / 线程 / 运行),并对外暴露标准 **Agent Protocol**(可被 LangGraph
Studio、Agent Chat UI、CopilotKit 直接连接)。

涉及的文件:

- [`aegra.json`](aegra.json):注册图 `deepagent -> ./src/deepagent/graph.py:graph`。
- [`graph.py`](src/deepagent/graph.py):0 参图工厂 `graph()`,内部调用
  `build_agent(platform_managed=True)`——**不带 checkpointer / store**,持久化交给 Aegra。
- `.env.example`:含 Aegra 部署变量(Postgres、端口、AUTH 等)。

启动(需 Python **≥ 3.12** 与 Docker):

```bash
uv sync --extra aegra        # 安装 aegra-cli(仅部署需要)
cp .env.example .env         # 填 OPENAI_API_KEY;按需改 Postgres
uv run aegra dev             # 用 Docker 起 Postgres + 开发服务(http://127.0.0.1:2026)
# 生产(自备 Postgres,Windows 不支持 serve):uv run aegra serve
```

客户端按 Agent Protocol 调用(`assistant_id` 即图 ID `deepagent`):

```python
from langgraph_sdk import get_client

client = get_client(url="http://127.0.0.1:2026")
thread = await client.threads.create()
async for chunk in client.runs.stream(
    thread_id=thread["thread_id"],
    assistant_id="deepagent",
    input={"messages": [{"type": "human", "content": "调研 LangGraph"}]},
    stream_mode=["messages-tuple"],
):
    print(chunk.data)
```

> 本地 / CLI 用进程内记忆;上 Aegra 时由平台用 Postgres 持久化。两条路径由
> `build_agent(platform_managed=...)` 区分:CLI 走 `managed_checkpointer=True`(内存),
> Aegra 走 `platform_managed=True`(不带 checkpointer,平台注入)。

## 设计说明

- **模型层**:litellm 网关暴露标准 OpenAI `/v1`,故用 `ChatOpenAI` 直连
  (litellm 官方推荐),`create_deep_agent` 接受 `BaseChatModel` 实例直接传入。
  聊天模型显式传 `base_url`/`api_key`,不依赖 `OPENAI_*`;但 `build_model` 会调用
  `export_openai_env()` 把网关回填到 `OPENAI_API_KEY`/`OPENAI_BASE_URL`,让 **embeddings**
  等其他 OpenAI 兼容组件(如 Aegra 语义 store)也走同一网关——只配 `AGENT_*` 即可。
- **shell 能力(跨平台)**:启用时用 `LocalShellBackend`,其 `execute` 工具基于
  `subprocess(shell=True)`,Windows 走 `cmd`、POSIX 走 `/bin/sh`,并继承 PATH
  等环境变量;关闭(`AGENT_ENABLE_SHELL=0`)时退回 `FilesystemBackend`,
  `execute` 会被自动过滤。不使用 bash-only 的 `ShellToolMiddleware`,以保证跨端可用。
- **记忆 / 持久化**:本地默认 **进程内** checkpointer / store(开发与单进程 CLI);
  生产交给 **Aegra**(Postgres,见上节)——图以 `platform_managed=True` 暴露,
  自身不带 checkpointer,持久层由平台运行时注入。
- **目录布局**:采用 `src/` 布局(PyPA 推荐),与 pip / pytest 等一致。
  同时是一个可被 `aegra dev` / `aegra serve` 直接加载的 Aegra 项目。

> 基于 deepagents `>=0.6.11`、langchain `1.3.x`、langgraph `1.2.x`。
> 代码内字符串为英文,注释与文档为中文。
