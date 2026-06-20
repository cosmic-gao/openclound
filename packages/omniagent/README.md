# omniagent

openclound 的 **通用 agent 基础包**,封装 [LangChain `deepagents`](https://github.com/langchain-ai/deepagents),
作为 **[Aegra](https://docs.aegra.dev) 项目**(self-hosted LangGraph Platform)以**多租户 + 双形态 + config 驱动**部署。

同一个图 `omniagent` 既能做**完整自由 ReAct**(像 Claude Code),又能做**结构化「检索→规划→执行→审核」管线**;每个 assistant 用 `config.configurable`(**opencode / Claude 风格**)自助开关,身份 / 租户由内网网关注入。

## 两种形态(`mode`)

| mode | 行为 | 适合 |
|---|---|---|
| **`react`**(默认) | 完整自由 ReAct 循环:think → tool → observe;`write_todos` 规划、文件系统、`task` 子代理 | 通用任务、编码、对话 |
| **`pipeline`** | 强制「**检索**(grep/文件/MCP/skill)→**规划**(todo)→**执行**→**审核**」,默认启用 `RubricMiddleware` 自评迭代 | 要求严谨、可验收的产出 |

`pipeline` 的"审核"是 deepagents `RubricMiddleware`:每次想结束时让 grader 子代理按 `rubric` 验收,不达标就打回继续,直到满足 / 失败 / 触顶。

## AgentConfig(per-assistant,放 `config.configurable`)

字段命名 / 结构对齐 **opencode.json / Claude Code**;全部可选,缺省继承 mode 默认或进程级 `Settings`:

| 字段 | 类型 | 说明 |
|---|---|---|
| `mode` | `react` \| `pipeline` | agent 形态(默认 `react`) |
| `model` | str | 覆盖模型(`provider` 由端点决定) |
| `prompt` | str | 场景系统指令(叠加在 mode 提示之后) |
| `temperature` | float | 采样温度 |
| `steps` | int | 最大模型迭代(opencode `steps`) |
| `tools` | `{name: bool}` | per-tool 开关,`false`=移除。名:`bash`/`write`/`edit`/`read`/`glob`/`grep`/`task` |
| `permission` | `{name: allow\|ask\|deny}` | `ask`→HITL 人工确认;`deny`→移除工具;`allow`→放行 |
| `review` | `{enabled, rubric, max_iterations}` | 审核(pipeline 默认开;无 `rubric` 则不激活) |
| `mcp` | `{name: {...}}` | per-agent MCP 检索源(`langchain-mcp-adapters` 连接格式) |

工具名映射:`bash→execute`、`write→write_file`、`edit→edit_file`、`read→read_file`、`glob`/`grep`/`task` 同名。

示例(pipeline + 审核 + 编辑需确认 + 接检索 MCP):

```jsonc
{
  "mode": "pipeline",
  "prompt": "你是严谨的研究助手,结论必须给来源。",
  "permission": { "edit": "ask" },
  "review": { "rubric": "每个结论都附可核验的来源链接", "max_iterations": 3 },
  "mcp": { "kb": { "transport": "streamable_http", "url": "http://kb:8000/mcp" } }
}
```

## 能力一览

| 能力 | 说明 |
|---|---|
| 双形态 | `react`(自由 ReAct)/ `pipeline`(检索→规划→执行→审核),`config.mode` 切换 |
| 任务规划 | 内置 `write_todos`,自动维护任务清单 |
| 文件系统 | `ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep`(真实磁盘,根=工作区) |
| Shell | `execute`,**跨平台**(Windows `cmd` / POSIX `/bin/sh`);`tools.bash=false` 关闭 |
| 子代理 | `task` 工具,隔离上下文执行子任务 |
| MCP | per-agent 经 `config.mcp` 挂载任意 MCP server 工具 |
| Skills | per-(tenant,agent) 磁盘 skill(`SKILL.md` + 多文件 / 脚本),热更新 |
| 审核 | `RubricMiddleware` 自评迭代(pipeline + `rubric`) |
| 健壮性 | 模型 / 工具自动重试、调用上限(`steps`)、备用模型回退 |
| 安全 | per-tool 裁剪 / HITL(`permission`)、可选 PII 脱敏 |
| 多租户 | 会话用户私有 + agent/skill 租户共享(Aegra 原生 + 内网网关);按 (user,tenant,agent) 装配 |

模型经 **OpenAI 兼容端点**(如 litellm 网关)接入,默认 `https://aigateway-sandbox.mspbots.ai/v1`,用 `ChatOpenAI` 对接,换模型只改一个环境变量(或 per-agent `config.model`)。

## 目录结构

```
packages/omniagent/
├── aegra.json              # Aegra 部署:注册图 omniagent -> graph.py:graph(async 工厂)
├── .env.example            # 进程级配置模板(OPENAI_* / AGENT_* / Aegra 部署变量)
├── src/omniagent/
│   ├── config.py           # Settings(进程级)+ AgentConfig/ReviewConfig(per-agent)+ parse
│   ├── modes.py            # mode 预设(react/pipeline)+ resolve():合并为 ResolvedConfig
│   ├── review.py           # RubricSeedMiddleware + build_review_middleware(审核装配)
│   ├── model.py            # build_model():经 OpenAI 兼容端点接入 ChatOpenAI
│   ├── mcp.py              # load_mcp_tools():加载 per-agent MCP server 工具
│   ├── middleware.py       # build_middleware():健壮性 / 上下文 / 安全
│   ├── workspace.py        # init_workspace + per-agent skill 源 + purge_agent
│   ├── skills.py           # save/list/delete_skill:per-agent skill 增删查(热更新)
│   ├── builder.py          # build_agent + ToolFilter:按 ResolvedConfig 组装
│   ├── graph.py            # Aegra async 工厂:按 (scope, config) 装配 + 缓存
│   ├── auth.py             # 内网身份:X-User-Id / X-Tenant-Id -> {identity, tenant}
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

## Aegra 部署(主形态)

Aegra 用 **Postgres 接管持久化**(checkpointer / 线程 / 运行),对外暴露标准 **Agent Protocol**。图工厂是 **async config 工厂** `async def graph(config)`(Aegra 每请求 `await` 调用,按签名注入 `config`),内部按 `(user, tenant, agent, 配置指纹)` 装配并缓存编译图,**不带 checkpointer / store**(平台注入)。

```bash
uv sync --extra aegra        # 安装 aegra-cli(仅部署需要)
cp .env.example .env         # 填 OPENAI_API_KEY;按需改 Postgres
uv run aegra dev             # Docker 起 Postgres + 开发服务(http://127.0.0.1:2026)
# 生产(自备 / 托管 Postgres,Windows 不支持 serve):
#   DATABASE_URL=… RUN_MIGRATIONS_ON_STARTUP=false uv run aegra serve
#   迁移交给 CI:aegra db upgrade
```

## 多租户 / 多 Agent

**两级模型,三方分工**——agent / 会话走 Aegra 原生,租户由内网网关注入,omniagent 只补 skill + 双模式装配:

```
终端用户 → 业务方网关(租户/RBAC/配额 · 身份注入 · 唯一入口)
         → Aegra:2026(+ omniagent,仅内网)→ Postgres + 本地磁盘
```

### 身份模型(内网信任,客户端不直连)

Aegra 仅内网部署,网关在内网注入身份头,[auth.py](src/omniagent/auth.py) 直接产出 `{identity, tenant}`(网络隔离即信任边界,**无 ServiceKey**):

| 操作 | 身份头 | identity | tenant |
|---|---|---|---|
| 运行(开会话 / 发消息) | `X-User-Id`=用户、`X-Tenant-Id`=租户 | **user** | 用户租户 |
| 管理(建 / 列 assistant、skill) | `X-User-Id`=租户 | **tenant** | — |

### 资源归属与隔离

| 资源 | key | 隔离 | 谁实现 |
|---|---|---|---|
| **assistant**(= agent) | `user_id = tenant` | 列表 / CRUD 租户级 | **Aegra 原生** `/assistants` |
| **会话** thread/run/历史 | `user_id = user` | **用户私有** | **Aegra 原生** `/threads` + checkpointer |
| **backend root**(skill + 运行期文件) | `tenant-<id>/assistant-<id>` | **per-assistant**(skill 在 `/skills`) | omniagent 磁盘 |

> Aegra 隔离锚定 `user_id`(= 鉴权 `identity`)。**assistant 读 = `OR(identity,"system")`、run 加载 assistant 不校验 owner** —— 故 `user_id=tenant` 即得租户级列表隔离,用户仍能 run 本租户 assistant;会话则 `user_id=user` 硬私有。**跨租户 run 的拦截由网关在入口做。**

### Skill(每个 agent 独立)

```
AGENT_WORKSPACE/tenant-<id>/assistant-<id>/  # 该 assistant 的 backend root(虚拟根)
├── skills/<skill>/SKILL.md (+ scripts/…)    # canonical skill,agent 经 /skills 读取(零复制)
└── …                                        # 运行期文件(execute / write_file)
```

skill 直接落在 assistant 的 backend root 下,agent 经虚拟路径 `/skills` 读取(无复制)。**热更新**:写 / 删磁盘 → **下个新会话** `before_agent` 自动重扫。两种写入:

1. 代码:`from omniagent import save_skill, list_skills, delete_skill`(见 [skills.py](src/omniagent/skills.py));
2. HTTP(管理身份,见 [http.py](src/omniagent/http.py)):`GET/PUT/DELETE /skills?agent=<id>`(PUT body `{"files": {...}}`)。

**删除 agent**:Aegra `DELETE /assistants/{id}` 只删记录、**无生命周期钩子**,故网关删除成功后应调 `DELETE /agents/{id}`(omniagent),删该 agent 的整个 backend root(`purge_agent`,返回 `{"purged": true}`)。

> 脚本类 skill **必须落盘**才能被 `execute` 执行。同一 assistant 的用户共享该 root 文件区,会话历史仍由 Aegra 按用户私有。

### 本地验证(curl,无 ServiceKey)

```bash
uv run aegra dev   # http://127.0.0.1:2026

# 建 react agent(管理身份 X-User-Id=租户)
curl -X POST http://127.0.0.1:2026/assistants -H "X-User-Id: acme" -H "Content-Type: application/json" \
  -d '{"assistant_id":"acme-react","graph_id":"omniagent","metadata":{"tenant":"acme"},"config":{"configurable":{"agent":"acme-react","mode":"react"}}}'

# 建 pipeline agent(审核 + 编辑需确认)
curl -X POST http://127.0.0.1:2026/assistants -H "X-User-Id: acme" -H "Content-Type: application/json" \
  -d '{"assistant_id":"acme-pipe","graph_id":"omniagent","metadata":{"tenant":"acme"},"config":{"configurable":{"agent":"acme-pipe","mode":"pipeline","permission":{"edit":"ask"},"review":{"rubric":"结论须附来源"}}}}'

# 列租户 agent(管理身份)
curl -X POST http://127.0.0.1:2026/assistants/search -H "X-User-Id: acme" -d '{}'

# 用户开会话并发消息(X-User-Id=用户、X-Tenant-Id=租户):会话私有
curl -X POST http://127.0.0.1:2026/threads -H "X-User-Id: alice" -H "X-Tenant-Id: acme" -d '{"thread_id":"alice-1","if_exists":"do_nothing"}'
curl -N -X POST http://127.0.0.1:2026/threads/alice-1/runs/stream -H "X-User-Id: alice" -H "X-Tenant-Id: acme" -H "Content-Type: application/json" \
  -d '{"assistant_id":"acme-react","input":{"messages":[{"type":"human","content":"hello"}]}}'
```

> 切 `X-User-Id` → 会话互不可见(Aegra 按 `identity` 私有);同 `X-Tenant-Id` 的 agent / skill 共享。

### 能力对照(优先 Aegra 原生)

| # | 需求 | 由谁 |
|---|---|---|
| 1 | agent 增删改查 / 列表 / 版本 | **Aegra 原生** `/assistants`(`user_id=tenant`) |
| 2 | 会话 / 历史 / 流式 / HITL | **Aegra 原生** `/threads` `/runs` + checkpointer |
| 3 | 持久化 / 已有库 / 迁移 | **Aegra 原生** Postgres · `DATABASE_URL` · `RUN_MIGRATIONS_ON_STARTUP` |
| 4 | 双形态(react/pipeline)+ per-agent 开关 | omniagent `config` + `modes.resolve` |
| 5 | per-agent skill(脚本、热更新) | omniagent 磁盘 + `/skills` |
| 6 | 工作区 per-user 隔离 / 删 agent 清理 | omniagent `graph.py` / `purge_agent` |
| 7 | 租户 / RBAC / 配额 / 身份注入 / run 校验 | 业务方网关 |

## 进程级配置(环境变量 / .env)

只放**部署级默认 / fallback**;per-agent 行为(mode/model/prompt/tools/permission/review/mcp)放 assistant config,不在这里。

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | 内置网关 | OpenAI 兼容 `/v1` 端点 |
| `OPENAI_API_KEY` | `anything` | 端点密钥 |
| `AGENT_MODEL` | `claude-sonnet-4-6` | 默认模型(可被 `config.model` 覆盖) |
| `AGENT_TEMPERATURE` | `0.0` | 默认温度(可被 `config.temperature` 覆盖) |
| `AGENT_FALLBACK_MODEL` | 空 | 主模型失败时的备用模型 |
| `AGENT_WORKSPACE` | `.agent` | backend 根;每个 assistant root=`tenant-<id>/assistant-<id>` |
| `AGENT_ENABLE_FILE_SEARCH` | `0` | ripgrep 文件搜索(deepagents 已有 glob/grep) |
| `AGENT_PII_STRATEGY` | `off` | PII 脱敏:`off`/`block`/`redact`/`mask`/`hash` |
| `AGENT_TOOL_CALL_LIMIT` | 空 | 单次运行工具调用上限(模型迭代上限是 per-agent `steps`) |
| `AGENT_MODEL_MAX_RETRIES` | `2` | 模型调用最大重试 |
| `AGENT_TOOL_MAX_RETRIES` | `2` | 工具调用最大重试 |
| `AGENT_CONTEXT_EDIT_TRIGGER_TOKENS` | `100000` | 触发清理旧工具输出的 token 阈值 |

## 设计说明

- **两层配置**:进程级 `Settings`(连接 / 默认 / fallback)+ 请求级 `AgentConfig`(opencode 风格 per-agent 开关);`modes.resolve` 按 `显式值 > mode 默认 > Settings` 合并为 `ResolvedConfig`,并把 `tools`/`permission` 推导成 deepagents 的 `excluded_tools` 与 `interrupt_on`。
- **模型层**:OpenAI 兼容端点暴露标准 `/v1`,用 `ChatOpenAI` 直连;`build_model` 调 `export_openai_env()` 把网关回填 `OPENAI_*`,让 embeddings 等也走同一端点。
- **shell(跨平台)**:`execute` 未被裁剪时用 `LocalShellBackend`(`subprocess(shell=True)`,Windows `cmd` / POSIX `/bin/sh`,继承 PATH);`tools.bash=false` 退回 `FilesystemBackend`。
- **持久化**:图以 platform-managed 暴露,自身不带 checkpointer / store,由 Aegra(Postgres)运行时注入。
- **安全**:Aegra 仅内网、客户端不直连;`user`/`tenant`/`agent`/skill 名经 `safe_segment` 校验,杜绝目录穿越。

> 基于 deepagents `>=0.6.11`、langchain `1.3.x`、langgraph `1.2.x`。
> 代码内字符串为英文,注释与文档为中文。
