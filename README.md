# agentos

openclound 的 **通用 agent 基础包**,封装 [LangChain `deepagents`](https://github.com/langchain-ai/deepagents),
作为 **[Aegra](https://docs.aegra.dev) 项目**(self-hosted LangGraph Platform)以 **config 驱动** 部署。

同一个图 `agentos` 既能做**完整自由 ReAct**(像 Claude Code),又能做**结构化「检索→规划→执行→审核」管线**;
每个 assistant 用 `config`(**opencode / Claude 风格**)自助开关。模型**统一经 `langchain_openai`** 接入任意
OpenAI 兼容端点 / 第三方网关(litellm 等)——**无任何默认,连接必须 per-assistant 显式分配**;skill 与跨会话
记忆**按 assistant 隔离**(无租户概念)。

## 单一形态(配置驱动)

只有**一种 deep agent**(完整 ReAct:think → tool → observe;`write_todos` 规划、文件系统、
`task` 子代理、skill、记忆)。**没有 `mode` 枚举**——行为差异全部由 `config` 表达:

- **自由 ReAct**(默认):直接用,无需额外配置。
- **检索→规划→执行→审核 管线**:把 `PIPELINE_PROMPT`(导出的纪律提示,或自定义)放进
  `config.prompt`,并设 `config.review.rubric` 开启自评迭代。

"审核"是 deepagents `RubricMiddleware`:每次想结束时让 grader 子代理按 `rubric` 验收,不达标
打回继续,直到满足 / 失败 / 触顶(默认 3 轮)。**给了 `review.rubric` 即自动开启**(显式
`review.enabled:false` 可关)。

## AgentConfig(per-assistant,放 assistant `config.configurable`)

字段命名 / 结构对齐 **opencode.json / Claude Code**,统一放在 assistant 的 `config.configurable`
(Agent Protocol 标准结构;运行时注入的鉴权 / `assistant_id` 也在此层)。

> ⚠️ **连接三件套 `model` / `base_url` / `api_key` 必须显式分配,无任何默认**;缺任一则该 assistant
> 运行时报错。

| 字段 | 类型 | 说明 |
|---|---|---|
| `model` | str | **必填**。模型名(传给兼容端点) |
| `base_url` | str | **必填**。OpenAI 兼容 `/v1` 端点(litellm 网关 / 任意兼容服务) |
| `api_key` | str | **必填**。端点密钥(⚠️ 入 config 即**明文存库**,`GET /assistants` 可读) |
| `prompt` | str | 场景系统指令(叠加在基础提示之后;放 `PIPELINE_PROMPT` 即得管线纪律) |
| `temperature` | float | 采样温度;仅显式设置时透传(不设默认) |
| `model_params` | `{...}` | 透传模型参数(`top_p`/`max_tokens`/`reasoning_effort`/`extra_body`;勿与上重复) |
| `steps` | int | 最大模型迭代(opencode `steps`) |
| `tools` | `{name: bool}` | per-tool 开关,`false`=移除。名:`bash`/`write`/`edit`/`read`/`glob`/`grep`/`task` |
| `permission` | `{name: allow\|ask\|deny}` | `ask`→HITL 人工确认;`deny`→移除工具;`allow`→放行 |
| `review` | `{enabled, rubric, max_iterations}` | 审核(pipeline 默认开;无 `rubric` 则不激活) |
| `mcp` | `{name: {...}}` | per-agent MCP 检索源(`langchain-mcp-adapters` 连接格式) |
| `memory` | bool | **跨会话持久记忆**(`/memories` → 平台 store);默认关 |
| `fallback_model` | str | 主模型失败时回退(同端点) |
| `pii_strategy` | `off\|block\|redact\|mask\|hash` | PII 脱敏 |
| `enable_file_search` | bool | ripgrep 文件搜索(已有 glob/grep) |

工具名映射:`bash→execute`、`write→write_file`、`edit→edit_file`、`read→read_file`、`glob`/`grep`/`task` 同名。

示例(pipeline + 审核 + 编辑需确认 + 跨会话记忆 + 接检索 MCP):

```jsonc
"config": {
  "configurable": {
    "model": "claude-sonnet-4-6",
    "base_url": "https://your-gateway/v1",
    "api_key": "sk-...",
    "prompt": "你是严谨的研究助手,结论必须给来源。",
    "permission": { "edit": "ask" },
    "review": { "rubric": "每个结论都附可核验的来源链接", "max_iterations": 3 },
    "memory": true,
    "mcp": { "kb": { "transport": "streamable_http", "url": "http://kb:8000/mcp" } }
  }
}
```

## 能力一览

| 能力 | 说明 |
|---|---|
| 单一形态 | 一种配置驱动 deep agent;管线纪律(`PIPELINE_PROMPT` + `review.rubric`)按需开 |
| 模型接入 | **统一 `langchain_openai`**,任意 OpenAI 兼容端点 / 网关;无默认,per-assistant 必填 |
| 任务规划 | 内置 `write_todos`,自动维护任务清单 |
| 文件系统 | `ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep`(真实磁盘,根=工作区) |
| Shell | `execute`,**跨平台**(Windows `cmd` / POSIX `/bin/sh`);`tools.bash=false` 关闭 |
| 子代理 | `task` 工具,隔离上下文执行子任务 |
| MCP | per-agent 经 `config.mcp` 挂载;**逐 server 容错**,单 server 失败仅跳过不拖垮 |
| Skills | per-agent 磁盘 skill(`SKILL.md` + 多文件 / 脚本),**按 assistant 隔离**,增删触发热重建 |
| **跨会话记忆** | `config.memory` 开启;`/memories` 路由到平台 store,按 assistant 命名空间持久 |
| 审核 | `RubricMiddleware` 自评迭代(pipeline + `rubric`) |
| 健壮性 | 模型 / 工具自动重试、调用上限(`steps`)、备用模型回退、长上下文清理 |
| 安全 | per-tool 裁剪 / HITL(`permission`)、可选 PII 脱敏、目录穿越防护 |
| 性能 | 编译图 LRU+TTL 缓存(`cachetools`)、per-key 锁(不同 assistant 冷启动并行) |

## 模型接入(统一 `langchain_openai`,无默认)

所有模型 / 第三方网关一律经 `langchain_openai.ChatOpenAI` 接入标准 `/v1`。**没有任何内置默认端点 / 密钥 /
模型**:`model` + `base_url` + `api_key` 必须由 assistant `config` 显式分配,缺任一即在构建时报错。换模型 /
换网关只改 assistant `config`,无需改代码或环境。

## 跨会话记忆(opt-in)

`config.memory: true` 时,backend 为 `CompositeBackend`:默认走本地工作区,`/memories/` 路由到 deepagents
`StoreBackend`——其 `store=None`,**运行时经 `langgraph.config.get_store()` 取 Aegra 注入的 Postgres store**,
故图编译期不带 store。记忆按 `("memories", <agent>)` 命名空间隔离、跨会话持久;`MemoryMiddleware` 启动时把
`/memories/AGENTS.md` 注入系统提示。`memory` 关闭(默认)则退化为纯本地 backend,无 store 依赖。

> 记忆依赖 Aegra 运行时注入的平台 store(Postgres),Aegra 默认提供。首次启用建议先做一次「写入→新会话读回」验证。

## 目录结构

```
.
├── aegra.json              # Aegra 部署:注册图 agentos -> graph.py:graph(async 工厂)
├── docker-compose.yml      # agentos 单服务,连外部托管 Postgres + Redis
├── Dockerfile              # 多阶段镜像(uv + aegra extra)
├── pyproject.toml          # uv 项目(依赖 / extra aegra / 工具配置)
├── .env.example            # 进程级运行参数 + 模型连接默认 + 外部 pg/redis
├── src/agentos/
│   ├── config.py           # Settings(运行参数)+ AgentConfig/ReviewConfig(per-agent,连接必填)+ parse
│   ├── spec.py             # resolve():合并 config 为 ResolvedConfig + fingerprint(无 mode)
│   ├── model.py            # build_model():统一经 langchain_openai 构造 ChatOpenAI(无默认)
│   ├── memory.py           # build_backend + memory_sources:跨会话记忆装配(CompositeBackend + StoreBackend)
│   ├── mcp.py              # load_mcp_tools():逐 server 容错加载 MCP 工具
│   ├── middleware.py       # 全部中间件:ToolFilter(裁剪)+ 审核装配 + 健壮性/上下文/PII
│   ├── builder.py          # build_agent:按 ResolvedConfig 组装 deep agent
│   ├── graph.py            # Aegra async 工厂:按 (agent, 配置+skill 指纹) 装配 + cachetools 缓存 + per-key 锁
│   ├── storage.py          # assistant 磁盘存储:路径/生命周期 + skill 发现与 CRUD
│   ├── auth.py             # 内网身份:X-User-Id -> {identity}(无租户)
│   └── http.py             # /skills + /agents/{agent} 管理路由(挂 aegra.json http.app)
└── tests/test_smoke.py
```

## 安装 / 开发

```bash
uv sync                 # 创建 .venv 并安装依赖(含 dev 组)
uv run pytest -q        # 测试
uv run ruff check .     # lint
uv run ruff format .    # 格式化
uv run mypy src         # 类型检查
```

## 部署(连外部托管 Postgres + Redis)

Aegra 用 **Postgres 接管持久化**(checkpointer / 线程 / 运行 / store),对外暴露标准 **Agent Protocol**。
图工厂是 **async config 工厂** `async def graph(config)`(Aegra 每请求 `await` 调用,按签名注入 `config`),
内部按 `(agent, 配置 + skill 指纹)` 装配并缓存编译图,**不带 checkpointer / store**(平台运行时注入)。

Postgres / Redis 均为**外部托管**(本地与生产一致),连接写在 `.env`:

```bash
cp .env.example .env         # 填外部 Postgres(POSTGRES_*)+ Redis(REDIS_URL);模型走 assistant config
```

**Docker(本地 / 生产,推荐)**——单 agentos 容器连外部 pg/redis:

```bash
docker compose up -d --build     # http://localhost:2026,启动时自动迁移
```

**进程直启**(本机已装 uv):

```bash
uv sync --extra aegra            # 安装 aegra-cli(Python >=3.12)
uv run aegra serve               # 连 .env 的外部 pg/redis;启动自动迁移
```

> 迁移在 `aegra serve` **启动时自动执行**(Alembic);Aegra CLI 无 `db` 子命令。
> 多实例横向扩展:`REDIS_BROKER_ENABLED=true` + 共享 `REDIS_URL`(Redis 队列分发 worker)。

## 多 Agent / 隔离(无租户)

**两方分工**——agent / 会话走 Aegra 原生,agentos 只补 skill + 记忆 + 双模式装配:

```
终端用户 → 业务方网关(RBAC/配额 · 身份注入 · 唯一入口)
         → Aegra:2026(+ agentos,仅内网)→ Postgres + 本地磁盘
```

### 身份模型(内网信任,客户端不直连)

Aegra 仅内网部署,网关在内网注入 `X-User-Id`,[auth.py](src/agentos/auth.py) 产出 `{identity}`
(网络隔离即信任边界,**无 ServiceKey、无租户**)。Aegra 据 `identity` 把 thread / run 按用户私有。

### 资源归属与隔离

| 资源 | 隔离 | 谁实现 |
|---|---|---|
| **assistant**(= agent) | 由 Aegra `/assistants` 管理(`user_id=identity` + `"system"` 共享) | **Aegra 原生** |
| **会话** thread/run/历史 | **用户私有**(按 `identity`) | **Aegra 原生** + checkpointer |
| **backend root**(skill + 运行期文件 + 记忆) | **per-assistant**(`<workspace>/<agent>`) | agentos 磁盘 + 平台 store |

> 跨资源访问控制由网关 / Aegra `@auth.on` 在入口做;agentos 只负责 per-assistant 的磁盘 / 记忆隔离。

### Skill(每个 assistant 独立)

```
AGENT_WORKSPACE/<agent>/                       # 该 assistant 的 backend root(虚拟根)
├── skills/<skill>/SKILL.md (+ scripts/…)      # canonical skill,agent 经 /skills 读取(零复制)
├── memories/                                   # (memory 开启时)跨会话记忆,经平台 store 持久
└── …                                           # 运行期文件(execute / write_file)
```

**热更新**:写 / 删 skill 磁盘 → 改变 skill 签名 → **下个新会话**自动重建图并重扫。两种写入:

1. 代码:`from agentos import list_skills, write_skill_file, delete_skill`(见 [storage.py](src/agentos/storage.py));
2. HTTP(见 [http.py](src/agentos/http.py)):`GET /skills` 与文件级 `GET/PUT/PATCH/DELETE /skills/{name}/files/{path}`(按 `agent=<id>`)。

**删除 agent**:Aegra `DELETE /assistants/{id}` 只删记录、无生命周期钩子,故网关删除成功后应调
`DELETE /agents/{id}`(agentos),删该 agent 的整个 backend root(`purge_agent`,返回 `{"purged": true}`)。

### 本地验证(curl)

```bash
uv run aegra serve   # http://127.0.0.1:2026(连 .env 的外部 pg/redis)

# 建 agent(连接放 config.configurable,必须显式分配)
curl -X POST http://127.0.0.1:2026/assistants -H "X-User-Id: acme" -H "Content-Type: application/json" \
  -d '{"assistant_id":"a1","graph_id":"agentos","config":{"configurable":{"agent":"a1","model":"claude-sonnet-4-6","base_url":"https://your-gateway/v1","api_key":"sk-..."}}}'

# 用户开会话并发消息(X-User-Id=用户):会话私有
curl -X POST http://127.0.0.1:2026/threads -H "X-User-Id: alice" -d '{"thread_id":"alice-1","if_exists":"do_nothing"}'
curl -N -X POST http://127.0.0.1:2026/threads/alice-1/runs/stream -H "X-User-Id: alice" -H "Content-Type: application/json" \
  -d '{"assistant_id":"a1","input":{"messages":[{"type":"human","content":"hello"}]}}'
```

## 进程级配置(环境变量 / .env)

**所有模型连接与 agent 行为都是 per-assistant**(放 assistant config);下表仅进程级运行参数兜底,
`.env` 实际只需 `AGENT_WORKSPACE` + Aegra 部署变量。

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_WORKSPACE` | `.agent` | backend 根;每个 assistant root=`<workspace>/<agent>` |
| `AGENT_ENABLE_FILE_SEARCH` | `0` | ripgrep 文件搜索(deepagents 已有 glob/grep) |
| `AGENT_PII_STRATEGY` | `off` | PII 脱敏:`off`/`block`/`redact`/`mask`/`hash` |
| `AGENT_TOOL_CALL_LIMIT` | 空 | 单次运行工具调用上限(模型迭代上限是 per-agent `steps`) |
| `AGENT_MODEL_MAX_RETRIES` | `2` | 模型调用最大重试 |
| `AGENT_TOOL_MAX_RETRIES` | `2` | 工具调用最大重试 |
| `AGENT_CONTEXT_EDIT_TRIGGER_TOKENS` | `100000` | 触发清理旧工具输出的 token 阈值 |

## 设计说明

- **两层配置**:进程级 `Settings`(仅运行参数,**无连接**)+ 请求级 `AgentConfig`(opencode 风格 per-agent
  开关 + 必填连接);`resolve()` 按 `显式 config > Settings` 合并为 `ResolvedConfig`,并把
  `tools`/`permission` 推导成 deepagents 的工具裁剪与 `interrupt_on`。
- **模型层**:统一 `langchain_openai.ChatOpenAI` 直连任意兼容端点;无默认,连接 per-assistant 必填。
- **工具裁剪**:deepagents 无 per-agent 裁剪公开参数(HarnessProfile 仅按字符串 model spec 生效,本包统一传
  实例故不命中),故用 `ToolFilter` 中间件在请求层移除被裁剪工具。
- **记忆**:`CompositeBackend` 把 `/memories` 路由到 `StoreBackend(store=None)`,运行时经 `get_store()` 取
  平台注入的 store;图编译期不带 store。
- **缓存 / 并发**:编译图用 `cachetools.TTLCache`(LRU+TTL)缓存,键含配置 + skill 指纹(剔除 api_key);
  per-key `asyncio.Lock` 去重并发构建,不同 assistant 冷启动互不阻塞。
- **shell(跨平台)**:`execute` 未裁剪时用 `LocalShellBackend`(Windows `cmd` / POSIX `/bin/sh`);
  `tools.bash=false` 退回 `FilesystemBackend`。
- **持久化**:图以 platform-managed 暴露,自身不带 checkpointer / store,由 Aegra(Postgres)运行时注入。
- **安全**:Aegra 仅内网、客户端不直连;`agent` / skill 名经 `safe_segment` 校验,杜绝目录穿越。

> 基于 deepagents `>=0.6.11`、langchain `1.3.x`、langgraph `1.2.x`。
> 代码内字符串为英文,注释与文档为中文。
