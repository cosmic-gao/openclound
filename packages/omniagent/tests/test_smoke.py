"""构造级冒烟测试:验证包可导入、各层可构建、agent 可编译,不真正调用模型。

覆盖重构后形态:**单一配置驱动 deep agent**(无 mode);统一 langchain_openai 模型层
(连接必填、无默认)、审核由 rubric 激活、跨会话记忆 opt-in、图缓存(cachetools + per-key
锁 + skill 感知)、无租户(scope 仅 agent)、MCP 单 server 容错。
"""

from __future__ import annotations

import asyncio

import pytest

#: 测试用占位连接(无默认端点,连接必须显式分配)。
_CONN = {"model": "m", "base_url": "https://x.test/v1", "api_key": "sk-x"}


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """每个用例独立临时工作区;重置图缓存与 per-key 锁(每用例独立 event loop)。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_WORKSPACE", str(tmp_path / "ws"))
    import omniagent.graph as _graph

    _graph._CACHE.clear()
    _graph._LOCKS.clear()


def _resolved(**cfg: object):  # type: ignore[no-untyped-def]
    """便捷:opencode 风格 configurable(默认带占位连接)→ ResolvedConfig。"""
    from omniagent import AgentConfig, get_settings, resolve

    return resolve(AgentConfig.parse({**_CONN, **cfg}), get_settings())


# ————————————————————————— 包元数据 / 导出 —————————————————————————


def test_package_metadata() -> None:
    import omniagent

    assert omniagent.__version__ == "0.1.0"
    for name in (
        "build_agent",
        "build_model",
        "build_backend",
        "build_middleware",
        "memory_sources",
        "get_settings",
        "load_mcp_tools",
        "Settings",
        "AgentConfig",
        "resolve",
    ):
        assert name in omniagent.__all__


# ————————————————————————— 进程级 Settings(无连接) —————————————————————————


def test_settings_has_no_connection() -> None:
    """连接(model/base_url/api_key)不再在 Settings —— 全部 per-assistant。"""
    from omniagent import get_settings

    s = get_settings()
    assert s.pii_strategy == "off"
    assert s.enable_file_search is False
    for removed in ("model", "base_url", "api_key", "temperature", "fallback_model"):
        assert not hasattr(s, removed)


def test_settings_runtime_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from omniagent import get_settings

    monkeypatch.setenv("AGENT_TOOL_CALL_LIMIT", "50")
    monkeypatch.setenv("AGENT_PII_STRATEGY", "mask")
    s = get_settings()
    assert s.tool_call_limit == 50
    assert s.pii_strategy == "mask"


# ————————————————————————— per-agent AgentConfig —————————————————————————


def test_parse_agent_config_defaults() -> None:
    from omniagent import AgentConfig

    cfg = AgentConfig.parse({})
    assert cfg.model is None
    assert cfg.base_url is None
    assert cfg.api_key is None
    assert cfg.memory is False
    assert cfg.review.enabled is None


def test_parse_agent_config_full() -> None:
    from omniagent import AgentConfig

    cfg = AgentConfig.parse(
        {
            "model": "gpt",
            "base_url": "https://e.test/v1",
            "api_key": "sk",
            "temperature": 0.3,
            "steps": 20,
            "tools": {"bash": False},
            "permission": {"edit": "ask"},
            "review": {"enabled": True, "rubric": "x", "max_iterations": 5},
            "mcp": {"kb": {"transport": "streamable_http", "url": "http://x"}},
            "memory": True,
        }
    )
    assert cfg.base_url == "https://e.test/v1"
    assert cfg.memory is True
    assert cfg.tools == {"bash": False}
    assert cfg.permission == {"edit": "ask"}
    assert cfg.review.rubric == "x"
    assert cfg.review.max_iterations == 5


def test_parse_agent_config_tolerates_bad() -> None:
    from omniagent import AgentConfig

    assert AgentConfig.parse({"tools": "not-a-dict"}).tools == {}


def test_parse_agent_config_ignores_scope_fields() -> None:
    from omniagent import AgentConfig

    cfg = AgentConfig.parse({"agent": "a1", "user_id": "u", "model": "m"})
    assert cfg.model == "m"


# ————————————————————————— resolve(配置驱动,无 mode) —————————————————————————


def test_resolve_defaults() -> None:
    from omniagent.resolve import DEFAULT_PROMPT

    r = _resolved()
    assert r.review_enabled is False
    assert r.prompt == DEFAULT_PROMPT
    assert r.excluded_tools == []
    assert r.interrupt_on == {}
    assert r.memory is False


def test_review_activates_on_rubric() -> None:
    """给 rubric → 自动开审核;没给 → 关;显式 enabled:false → 关。"""
    assert _resolved(review={"rubric": "x"}).review_enabled is True
    assert _resolved().review_enabled is False
    assert _resolved(review={"rubric": "x", "enabled": False}).review_enabled is False


def test_pipeline_prompt_opt_in() -> None:
    """纪律提示按需注入 config.prompt(不再有 pipeline mode)。"""
    from omniagent.resolve import PIPELINE_PROMPT

    r = _resolved(prompt=PIPELINE_PROMPT)
    assert "RETRIEVE" in r.prompt


def test_resolve_tools_permission_to_excluded_interrupt() -> None:
    r = _resolved(tools={"bash": False}, permission={"edit": "ask", "write": "deny"})
    assert "execute" in r.excluded_tools
    assert "write_file" in r.excluded_tools
    assert r.interrupt_on == {"edit_file": True}


def test_resolve_prompt_appends_user() -> None:
    from omniagent.resolve import DEFAULT_PROMPT

    r = _resolved(prompt="SCENE")
    assert r.prompt.startswith(DEFAULT_PROMPT)
    assert r.prompt.endswith("SCENE")


def test_resolve_passes_connection() -> None:
    r = _resolved(
        model="m2",
        base_url="https://y.test/v1",
        api_key="sk-y",
        temperature=0.9,
        memory=True,
    )
    assert r.model == "m2"
    assert r.base_url == "https://y.test/v1"
    assert r.api_key == "sk-y"
    assert r.temperature == pytest.approx(0.9)
    assert r.memory is True


# ————————————————————————— 模型(统一 langchain_openai,无默认) —————————————————————————


def test_build_model_requires_connection() -> None:
    from omniagent import build_model

    with pytest.raises(ValueError, match="model"):
        build_model(model=None, base_url="https://x.test/v1", api_key="sk")
    with pytest.raises(ValueError, match="base_url"):
        build_model(model="m", base_url=None, api_key="sk")
    with pytest.raises(ValueError, match="api_key"):
        build_model(model="m", base_url="https://x.test/v1", api_key=None)


def test_build_model_constructs() -> None:
    from langchain_openai import ChatOpenAI

    from omniagent import build_model

    m = build_model(model="m", base_url="https://x.test/v1", api_key="sk-z")
    assert isinstance(m, ChatOpenAI)
    assert m.model_name == "m"
    assert str(m.openai_api_base) == "https://x.test/v1"
    assert m.openai_api_key.get_secret_value() == "sk-z"


def test_build_model_temperature_and_params() -> None:
    from omniagent import build_model

    m = build_model(
        model="m",
        base_url="https://x.test/v1",
        api_key="sk",
        temperature=0.42,
        model_params={"top_p": 0.9},
    )
    assert m.temperature == pytest.approx(0.42)
    assert m.top_p == pytest.approx(0.9)


# ————————————————————————— 记忆(opt-in)/ backend —————————————————————————


def test_build_backend_local_without_memory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from deepagents.backends import (
        CompositeBackend,
        FilesystemBackend,
        LocalShellBackend,
    )

    from omniagent.memory import build_backend

    b = build_backend(_resolved(memory=False), tmp_path, "a1")
    assert isinstance(b, LocalShellBackend)
    assert not isinstance(b, CompositeBackend)
    # execute 裁剪 → 纯文件 backend(无 execute)
    b2 = build_backend(_resolved(memory=False, tools={"bash": False}), tmp_path, "a1")
    assert isinstance(b2, FilesystemBackend)
    assert not isinstance(b2, LocalShellBackend)


def test_build_backend_composite_with_memory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from deepagents.backends import CompositeBackend

    from omniagent.memory import MEMORY_ROUTE, build_backend

    b = build_backend(_resolved(memory=True), tmp_path, "a1")
    assert isinstance(b, CompositeBackend)
    assert MEMORY_ROUTE in b.routes


def test_memory_sources() -> None:
    from omniagent.memory import MEMORY_FILE, memory_sources

    assert memory_sources(_resolved(memory=True)) == [MEMORY_FILE]
    assert memory_sources(_resolved(memory=False)) is None


# ————————————————————————— 中间件 / 审核 —————————————————————————


def test_build_middleware_default() -> None:
    from omniagent import build_middleware, get_settings

    mw = build_middleware(_resolved(), get_settings(), workspace_root=".")
    names = {type(m).__name__ for m in mw}
    assert "ModelRetryMiddleware" in names
    assert "ToolRetryMiddleware" in names
    assert "ContextEditingMiddleware" in names


def test_build_middleware_steps_and_fallback() -> None:
    from omniagent import build_middleware, get_settings

    mw = build_middleware(
        _resolved(steps=30, fallback_model="fb"), get_settings(), workspace_root="."
    )
    names = {type(m).__name__ for m in mw}
    assert "ModelCallLimitMiddleware" in names
    assert "ModelFallbackMiddleware" in names


def test_rubric_seed_middleware_injects() -> None:
    from omniagent.review import RubricSeedMiddleware

    mw = RubricSeedMiddleware("RUBRIC")
    assert mw.before_agent({}, None) == {"rubric": "RUBRIC"}  # type: ignore[arg-type]
    assert mw.before_agent({"rubric": "x"}, None) is None  # type: ignore[arg-type]


def test_build_review_middleware() -> None:
    from deepagents.middleware.rubric import RubricMiddleware

    from omniagent import build_model
    from omniagent.review import RubricSeedMiddleware, build_review_middleware

    model = build_model(model="m", base_url="https://x.test/v1", api_key="sk")
    pipe = build_review_middleware(_resolved(review={"rubric": "x"}), model)
    assert [type(m) for m in pipe] == [RubricSeedMiddleware, RubricMiddleware]
    assert build_review_middleware(_resolved(), model) == []  # 无 rubric
    assert build_review_middleware(_resolved(review={"enabled": True}), model) == []


# ————————————————————————— 工作区 / skill —————————————————————————


def test_agent_root_no_tenant(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """backend root = <base>/<agent>(无 tenant 层)。"""
    from omniagent.config import resolve_path
    from omniagent.workspace import agent_root

    root = agent_root(tmp_path, "a1")
    assert root == resolve_path(tmp_path) / "a1"


def test_skill_sources_and_signature(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import save_skill
    from omniagent.workspace import skill_signature, skill_sources

    root = tmp_path / "agent"
    assert skill_sources(root) == []
    assert skill_signature(root) == ""
    save_skill(root, "demo", {"SKILL.md": "---\nname: demo\ndescription: d\n---\n"})
    assert skill_sources(root) == ["/skills"]
    sig1 = skill_signature(root)
    assert "demo" in sig1
    # 增 skill → 签名变化(触发图重建)
    save_skill(root, "more", {"SKILL.md": "---\nname: more\ndescription: d\n---\n"})
    assert skill_signature(root) != sig1


def test_load_mcp_tools_empty() -> None:
    from omniagent import load_mcp_tools

    assert asyncio.run(load_mcp_tools({})) == []


def test_load_mcp_tools_fault_isolation() -> None:
    """单个不可达 / 坏 server 不抛异常,仅跳过(返回可用子集)。"""
    from omniagent import load_mcp_tools

    servers = {
        "bad": {"transport": "stdio", "command": "nonexistent_cmd_xyz", "args": []}
    }
    assert asyncio.run(load_mcp_tools(servers)) == []


# ————————————————————————— agent 组装(builder) —————————————————————————


def test_build_agent_constructs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import build_agent

    agent = build_agent(
        resolved=_resolved(),
        workspace=str(tmp_path / "ws"),
        skill_sources=[],
        agent="a1",
    )
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "astream")
    # 纯 Aegra 形态:持久化交给平台,图本身不带 checkpointer / store。
    assert agent.checkpointer is None
    assert agent.store is None


def test_build_agent_exposes_default_tools(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import build_agent

    agent = build_agent(
        resolved=_resolved(),
        workspace=str(tmp_path / "ws"),
        skill_sources=[],
        agent="a1",
    )
    registered = {
        t.name
        for t in agent.nodes["tools"].bound._tools_by_name.values()  # type: ignore[attr-defined]
    }
    assert "execute" in registered
    assert {"read_file", "write_file", "edit_file", "glob", "grep"} <= registered


def test_tool_filter() -> None:
    from omniagent.builder import ToolFilter, _tool_name

    assert _tool_name({"name": "write_file"}) == "write_file"

    class _Req:
        def __init__(self, tools: list[dict[str, str]]) -> None:
            self.tools = tools

        def override(self, *, tools: list[dict[str, str]]) -> _Req:
            return _Req(tools)

    out = ToolFilter({"write_file"})._filter(
        _Req([{"name": "write_file"}, {"name": "read_file"}])  # type: ignore[arg-type]
    )
    assert [t["name"] for t in out.tools] == ["read_file"]


# ————————————————————————— Aegra 图工厂(async) —————————————————————————


def test_graph_factory_async() -> None:
    """omniagent.graph:graph 是 async 工厂,产出无 checkpointer 的平台托管图。"""
    from omniagent.graph import graph

    g = asyncio.run(graph({"configurable": dict(_CONN)}))
    assert hasattr(g, "invoke")
    assert hasattr(g, "astream")
    assert g.checkpointer is None  # Aegra 注入 Postgres 持久化


def test_graph_resolve_scope() -> None:
    """工厂图 scope 仅 agent(无租户);缺省回退 default。"""
    from omniagent.graph import _resolve_scope

    assert _resolve_scope({"configurable": {"agent": "a1"}}) == "a1"
    assert _resolve_scope({}) == "default"
    assert _resolve_scope({"agent": "a2"}) == "a2"
    # 缺 agent 回退平台 assistant_id(避免多 assistant 撞 "default");agent 优先
    assert _resolve_scope({"configurable": {"assistant_id": "asst_x"}}) == "asst_x"
    assert _resolve_scope({"agent": "a", "assistant_id": "x"}) == "a"


def test_graph_rejects_bad_agent() -> None:
    """工厂图对穿越式 agent 直接拒绝。"""
    from omniagent.graph import graph

    with pytest.raises(ValueError):
        asyncio.run(graph({"configurable": {"agent": "../escape", **_CONN}}))


def test_graph_caches_per_scope_and_config() -> None:
    """同 (agent,指纹) 复用;不同 agent / 审核配置独立。"""
    from omniagent.graph import graph

    base = {"agent": "a1", **_CONN}

    async def run() -> tuple[object, ...]:
        g1 = await graph({"configurable": dict(base)})
        same = await graph({"configurable": dict(base)})
        diff_agent = await graph({"configurable": {**base, "agent": "a2"}})
        diff_review = await graph({"configurable": {**base, "review": {"rubric": "x"}}})
        return g1, same, diff_agent, diff_review

    g1, same, diff_agent, diff_review = asyncio.run(run())
    assert same is g1
    assert diff_agent is not g1
    assert diff_review is not g1


def test_graph_rebuilds_on_skill_change() -> None:
    """新增 skill 改变指纹 → 重建(非同一图)。"""
    from omniagent import get_settings, save_skill
    from omniagent.graph import graph
    from omniagent.workspace import agent_root

    base = {"agent": "a1", **_CONN}

    async def run() -> tuple[object, object]:
        g1 = await graph({"configurable": dict(base)})
        root = agent_root(get_settings().workspace, "a1")
        save_skill(root, "s", {"SKILL.md": "---\nname: s\ndescription: d\n---\n"})
        g2 = await graph({"configurable": dict(base)})
        return g1, g2

    g1, g2 = asyncio.run(run())
    assert g2 is not g1


def test_flat_config_without_configurable() -> None:
    """扁平 config(无 configurable 包裹)等价于 config.configurable。"""
    from omniagent.graph import _configurable, _resolve_scope

    assert _resolve_scope({"agent": "a1"}) == "a1"
    assert _configurable({"model": "m"})["model"] == "m"
    # configurable 优先(承载运行时注入)
    merged = _configurable({"model": "a", "configurable": {"model": "b"}})
    assert merged["model"] == "b"


# ————————————————————————— auth(内网,identity-only) —————————————————————————


def test_auth_resolve_identity() -> None:
    """内网信任:读 X-User-Id 为 identity;无租户维度。"""
    from omniagent.auth import resolve_identity

    assert resolve_identity({"x-user-id": "alice"}) == {"identity": "alice"}
    assert resolve_identity({}) == {"identity": "anonymous"}
    assert "tenant" not in resolve_identity({"x-user-id": "a", "x-tenant-id": "t"})


# ————————————————————————— skill CRUD / 安全 —————————————————————————


def test_skill_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import delete_skill, list_skills, save_skill

    root = tmp_path / "agent"
    save_skill(
        root,
        "my",
        {"SKILL.md": "---\nname: my\ndescription: d\n---\n", "scripts/run.py": "x=1"},
    )
    assert "my" in list_skills(root)
    assert (root / "skills" / "my" / "scripts" / "run.py").is_file()
    assert delete_skill(root, "my") is True
    assert "my" not in list_skills(root)


def test_skill_rejects_traversal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import save_skill

    with pytest.raises(ValueError):
        save_skill(tmp_path, "../evil", {"SKILL.md": "x"})
    with pytest.raises(ValueError):
        save_skill(tmp_path, "ok", {"../evil.py": "x"})
    with pytest.raises(ValueError):
        save_skill(tmp_path, "ok", {"a.txt": "x"})


def test_safe_segment_rejects_traversal() -> None:
    from omniagent.config import safe_segment

    assert safe_segment("ok") == "ok"
    for bad in ("", ".", "..", "a/b", "a\\b"):
        with pytest.raises(ValueError):
            safe_segment(bad)


def test_purge_agent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import purge_agent, save_skill

    root = tmp_path / "agent"
    save_skill(root, "s", {"SKILL.md": "---\nname: s\ndescription: d\n---\n"})
    (root / "notes.txt").write_text("scratch", encoding="utf-8")
    assert purge_agent(root) is True
    assert not root.exists()
    assert purge_agent(root) is False


def test_http_routes() -> None:
    """skill CRUD + agent 清理路由(按 agent 单维)。"""
    pytest.importorskip("fastapi")
    pytest.importorskip("aegra_api")
    from omniagent.http import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/skills", "/skills/{name}", "/agents/{agent}"} <= paths
