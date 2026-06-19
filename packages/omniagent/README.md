# omniagent

openclound 的 **通用 agent 基础包**,封装 [LangChain `deepagents`](https://github.com/langchain-ai/deepagents),
集成 **OpenAI 兼容端点 / MCP / skills / 长短期记忆 / 安全中间件**,
作为 **[Aegra](https://docs.aegra.dev) 项目**(self-hosted LangGraph Platform)以多租户 / 多 Agent 形式部署。

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
| 多租户 | 工厂图按 (tenant, agent) 装配 skill 与场景,公有 + 私有 skill 隔离 |

模型经 **litellm 网关**(OpenAI 兼容)接入,默认指向
`https://aigateway-sandbox.mspbots.ai/v1`,用 `ChatOpenAI` 对接,因此无需直连
各家厂商 SDK,换模型只改一个环境变量。

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)(包 / 环境管理)
- 环境变量 `OPENAI_API_KEY`(模型端点密钥;连接走标准 OpenAI 变量)

## 目录结构

```
packages/omniagent/
├── pyproject.toml          # uv_build(src 布局) + ruff/mypy/pytest
├── aegra.json              # Aegra 部署配置:注册图 omniagent -> graph.py:graph
├── .env.example            # 配置模板(AGENT_* + Aegra 部署变量)
├── README.md
├── src/
│   └── omniagent/
│       ├── __init__.py     # 公共 API 导出
│       ├── config.py       # Settings(pydantic-settings)+ get_settings(读 OPENAI_*/AGENT_*/.env)
│       ├── model.py        # build_model():经 OpenAI 兼容端点接入 ChatOpenAI
│       ├── mcp.py          # load_mcp_tools():加载 MCP server 工具
│       ├── middleware.py   # build_middleware() / interrupts()
│       ├── workspace.py    # init_workspace() + 公有/租户 skill 源解析
│       ├── skills.py       # save/list/delete_skill():私有 skill 增删查(热更新)
│       ├── builder.py      # build_agent() / build_async_agent() 入口
│       ├── graph.py        # Aegra 工厂图:按 (tenant, agent) 装配 skill 与场景
│       ├── http.py         # skill 管理 HTTP 路由(挂 aegra.json http.app)
│       ├── _data/          # 随包模板:skills/ 与 memories/AGENTS.md
│       └── py.typed
└── tests/
    └── test_smoke.py
```

## 安装 / 开发

```bash
# 在包目录内(或从仓库根加 --directory packages/omniagent)
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
from omniagent import build_agent

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
from omniagent import build_async_agent

async def main():
    agent = await build_async_agent(mcp_servers={
        "fs": {"transport": "stdio", "command": "python", "args": ["server.py"]},
        "weather": {"transport": "streamable_http", "url": "http://localhost:8000/mcp"},
    })
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "..."}]})
    print(result["messages"][-1].content)

asyncio.run(main())
```

> 生产形态是 **Aegra 部署**(见下文「Aegra 部署」),由平台对外暴露 Agent
> Protocol 接口;上面两种用法用于本地嵌入 / 测试。

## 配置(环境变量 / .env)

推荐用 `.env`:复制模板后填入网关密钥即可(`.env` 已被 `.gitignore` 忽略):

```bash
cp .env.example .env        # 然后编辑 .env,至少填 OPENAI_API_KEY
```

`get_settings()` 启动时会自动加载**当前工作目录**下的 `.env`。优先级:
**shell 环境变量 > `.env` > 代码默认值**。各项均有合理默认值:

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | 内置网关 | OpenAI 兼容 `/v1` 端点(留空用默认网关;可指向 MiniMax 等) |
| `OPENAI_API_KEY` | `anything` | 端点密钥 |
| `AGENT_MODEL` | `claude-sonnet-4-6` | 模型名(由网关路由) |
| `AGENT_TEMPERATURE` | `0.0` | 采样温度 |
| `AGENT_FALLBACK_MODEL` | 空 | 主模型失败时的备用模型 |
| `AGENT_WORKSPACE` | `.agent` | 工作区目录(agent 的文件系统根) |
| `AGENT_SKILLS_ROOT` | `.agent/skills` | skill 根:`public/`(公有)+ `<tenant>/<agent>/`(私有) |
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

- [`aegra.json`](aegra.json):注册图 `omniagent -> ./src/omniagent/graph.py:graph`。
- [`graph.py`](src/omniagent/graph.py):0 参图工厂 `graph()`,内部调用
  `build_agent(platform_managed=True)`——**不带 checkpointer / store**,持久化交给 Aegra。
- `.env.example`:含 Aegra 部署变量(Postgres、端口、AUTH 等)。

启动(需 Python **≥ 3.12** 与 Docker):

```bash
uv sync --extra aegra        # 安装 aegra-cli(仅部署需要)
cp .env.example .env         # 填 OPENAI_API_KEY;按需改 Postgres
uv run aegra dev             # 用 Docker 起 Postgres + 开发服务(http://127.0.0.1:2026)
# 生产(自备 Postgres,Windows 不支持 serve):uv run aegra serve
```

客户端按 Agent Protocol 调用(`assistant_id` 即图 ID `omniagent`):

```python
from langgraph_sdk import get_client

client = get_client(url="http://127.0.0.1:2026")
thread = await client.threads.create()
async for chunk in client.runs.stream(
    thread_id=thread["thread_id"],
    assistant_id="omniagent",
    input={"messages": [{"type": "human", "content": "调研 LangGraph"}]},
    stream_mode=["messages-tuple"],
):
    print(chunk.data)
```

> 本地嵌入用进程内记忆;上 Aegra 时由平台用 Postgres 持久化。两条路径由
> `build_agent(platform_managed=...)` 区分:本地走 `managed_checkpointer=True`(内存),
> Aegra 走 `platform_managed=True`(不带 checkpointer,平台注入)。

## 多租户 / 多 Agent(Agent OS)

模型:**租户**(鉴权身份)→ N 个 **Agent**(各有场景)→ 每次聊天一个**会话**。

| 概念 | 映射 | 隔离 |
|---|---|---|
| 租户 | 鉴权 `tenant_id` | Aegra authz 过滤 assistant/thread |
| Agent | 一个 Aegra **assistant**(`config={agent_id, system_prompt}` + `metadata={tenant_id}`) | 按租户过滤 |
| 会话 | 一个 **thread**(每次聊天新建) | Postgres 按 `thread_id` |

工厂图 [graph.py](src/omniagent/graph.py) 每次 run 从 `config` 取 **租户(鉴权)+ agent(assistant 配置)**,拼出 skill 源并装配场景。

**Skill 三层(公有 + 私有,磁盘目录):**

```
AGENT_SKILLS_ROOT/
├── public/<skill>/SKILL.md            # 公有:所有租户所有 agent 共享(从 _data 初始化)
└── <tenant>/<agent>/<skill>/          # 私有:仅该租户该 agent;可含多文件 + 脚本
    └── SKILL.md (+ scripts/…, …)
```

skill 源 = `[public, <tenant>/<agent>]`(同名私有覆盖公有)。

**热更新**:往私有目录写/删文件 → **下一个新会话**自动重扫加载(`before_agent`),无需重启。写入有两种方式:

1. 代码:`from omniagent import save_skill, list_skills, delete_skill`(纯函数,见 [skills.py](src/omniagent/skills.py));
2. HTTP(挂在 `aegra.json` 的 `http.app`,见 [http.py](src/omniagent/http.py)):
   - `GET /skills?agent_id=…` 列出 · `PUT /skills/{name}?agent_id=…` 写入(body `{"files": {...}}`)· `DELETE /skills/{name}` 删除
   - 租户取自鉴权身份(请按你的 Aegra auth 调整 `_tenant()`)。

> 脚本类 skill **必须在磁盘**才能被 `execute` 执行(`StoreBackend`/Postgres 跑不了脚本);多副本时让各副本共享/同步该 skill 目录即可。

### 能力对照(谁负责)

| # | 需求 | 由谁实现 | 接口 / 位置 |
|---|---|---|---|
| 1 | 每租户每 Agent 独立 | **Aegra**(assistant)+ 我方按 `agent_id` 装配独立 skill/work | `POST /assistants` · `graph.py` |
| 2 | 用户会话独立 | **Aegra**(thread,Postgres 按 `thread_id`,归属 assistant+租户) | `POST /threads` · runs |
| 3 | 全租户共享 public skill | **我方** | `seed_public_skills` + 公有源 |
| 4 | 每 Agent 私有 skill 增删改查 | **我方** | `save/list/delete_skill` · `GET/PUT/DELETE /skills` |
| 5 | 查 Agent 在线/可用状态 | **Aegra 原生**(可用=存在)+ 我方 skill 就绪 | `GET /assistants/{id}` · `GET /skills?agent_id=…` |
| 6 | 查租户 Agent 列表 | **Aegra 原生** | `GET /assistants` · `POST /assistants/search`(按租户过滤) |
| 7 | 删租户下 Agent | **Aegra 原生**删记录 + **我方**清文件 | `DELETE /assistants/{id}` + `purge_agent()` |

> 注册 / 列表 / 删除记录 / 可用状态(#1#6#7#5)全部走 Aegra 原生 `/assistants`,**不重复造**。
> 我方只补 Aegra **没有**的:公有/私有 skill(#3#4,含脚本、热更新)与删 agent 后的文件清理
> (#7 的 `purge_agent()`,接到你的删除流程里)。配置型 agent "在线"即"已注册",故 #5 用
> `GET /assistants/{id}` 判存在 + 我方 `GET /skills` 看 skill 就绪即可,无需额外探测接口。
> 安全:`tenant` 始终取自鉴权身份;`tenant`/`agent`/skill 名经 `safe_segment` 校验,杜绝目录穿越。

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
- **记忆 / 持久化**:本地默认 **进程内** checkpointer / store(开发与库调用);
  生产交给 **Aegra**(Postgres,见上节)——图以 `platform_managed=True` 暴露,
  自身不带 checkpointer,持久层由平台运行时注入。
- **目录布局**:采用 `src/` 布局(PyPA 推荐),与 pip / pytest 等一致。
  同时是一个可被 `aegra dev` / `aegra serve` 直接加载的 Aegra 项目。

> 基于 deepagents `>=0.6.11`、langchain `1.3.x`、langgraph `1.2.x`。
> 代码内字符串为英文,注释与文档为中文。
