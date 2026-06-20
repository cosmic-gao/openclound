"""构造级冒烟测试:验证包可导入、各层可构建、agent 可编译,不真正调用模型。"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """每个用例使用独立临时工作区与占位密钥,避免网络与污染 cwd;重置图缓存与锁。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("AGENT_SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-placeholder")
    for var in ("AGENT_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    # 清空工厂图缓存并重建锁(每个用例独立 event loop,锁不可跨 loop 复用)。
    import omniagent.graph as _graph

    _graph._CACHE.clear()
    _graph._LOCK = asyncio.Lock()


def _resolved(**cfg: object):  # type: ignore[no-untyped-def]
    """便捷:把 opencode 风格 configurable 解析 + 合并为 ResolvedConfig。"""
    from omniagent import AgentConfig, get_settings, resolve

    return resolve(AgentConfig.parse(cfg), get_settings())


# ————————————————————————— 包元数据 / 导出 —————————————————————————


def test_package_metadata() -> None:
    import omniagent

    assert omniagent.__version__ == "0.1.0"
    for name in (
        "build_agent",
        "build_model",
        "build_middleware",
        "get_settings",
        "load_mcp_tools",
        "Settings",
        "AgentConfig",
        "resolve",
    ):
        assert name in omniagent.__all__


# ————————————————————————— 进程级 Settings —————————————————————————


def test_settings_defaults() -> None:
    from omniagent import GATEWAY_BASE_URL, get_settings

    s = get_settings()
    assert s.base_url == GATEWAY_BASE_URL
    assert s.model == "claude-sonnet-4-6"
    assert s.pii_strategy == "off"
    assert s.enable_file_search is False
    assert not hasattr(s, "service_key")  # ServiceKey 已移除


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from omniagent import get_settings

    monkeypatch.setenv("AGENT_MODEL", "gpt-5.1")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.7")
    s = get_settings()
    assert s.model == "gpt-5.1"
    assert s.temperature == pytest.approx(0.7)


def test_settings_reads_openai_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """连接走标准 OPENAI_BASE_URL / OPENAI_API_KEY(可指向任意兼容端点)。"""
    from omniagent import get_settings

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mm")
    s = get_settings()
    assert s.base_url == "https://api.minimaxi.com/v1"
    assert s.api_key == "sk-test-mm"


# ————————————————————————— per-agent AgentConfig —————————————————————————


def test_parse_agent_config_defaults() -> None:
    from omniagent import AgentConfig

    cfg = AgentConfig.parse({})
    assert cfg.mode == "react"
    assert cfg.model is None
    assert cfg.tools == {}
    assert cfg.permission == {}
    assert cfg.review.enabled is None


def test_parse_agent_config_opencode_style() -> None:
    from omniagent import AgentConfig

    cfg = AgentConfig.parse(
        {
            "mode": "pipeline",
            "model": "gpt-5.1",
            "prompt": "scene",
            "temperature": 0.3,
            "steps": 20,
            "tools": {"bash": False},
            "permission": {"edit": "ask"},
            "review": {"enabled": True, "rubric": "must pass", "max_iterations": 5},
            "mcp": {"kb": {"transport": "streamable_http", "url": "http://x"}},
        }
    )
    assert cfg.mode == "pipeline"
    assert cfg.model == "gpt-5.1"
    assert cfg.tools == {"bash": False}
    assert cfg.permission == {"edit": "ask"}
    assert cfg.review.rubric == "must pass"
    assert cfg.review.max_iterations == 5
    assert cfg.mcp["kb"]["url"] == "http://x"


def test_parse_agent_config_ignores_scope_fields() -> None:
    """configurable 里的 scope / 鉴权字段被忽略(extra=ignore),不影响解析。"""
    from omniagent import AgentConfig

    cfg = AgentConfig.parse(
        {
            "agent": "a1",
            "user_id": "u",
            "langgraph_auth_user": object(),
            "mode": "pipeline",
        }
    )
    assert cfg.mode == "pipeline"


def test_parse_agent_config_tolerates_bad() -> None:
    """字段类型错误时整体回退默认,不抛异常(容错)。"""
    from omniagent import AgentConfig

    assert AgentConfig.parse({"tools": "not-a-dict"}).mode == "react"


# ————————————————————————— modes:resolve —————————————————————————


def test_resolve_react_defaults() -> None:
    from omniagent.modes import REACT_PROMPT

    r = _resolved(mode="react")
    assert r.mode == "react"
    assert r.review_enabled is False
    assert r.prompt == REACT_PROMPT
    assert r.excluded_tools == []
    assert r.interrupt_on == {}


def test_resolve_pipeline_enables_review() -> None:
    r = _resolved(mode="pipeline", review={"rubric": "x"})
    assert r.review_enabled is True
    assert r.rubric == "x"
    assert "RETRIEVE" in r.prompt  # pipeline 提示


def test_resolve_tools_permission_to_excluded_interrupt() -> None:
    r = _resolved(tools={"bash": False}, permission={"edit": "ask", "write": "deny"})
    assert "execute" in r.excluded_tools  # bash:false
    assert "write_file" in r.excluded_tools  # write:deny
    assert r.interrupt_on == {"edit_file": True}  # edit:ask


def test_resolve_prompt_appends_user() -> None:
    r = _resolved(mode="react", prompt="SCENE")
    assert r.prompt.endswith("SCENE")


def test_resolve_model_temperature_override() -> None:
    r = _resolved(model="m2", temperature=0.9)
    assert r.model == "m2"
    assert r.temperature == pytest.approx(0.9)


# ————————————————————————— 模型 —————————————————————————


def test_build_model_targets_gateway() -> None:
    from langchain_openai import ChatOpenAI

    from omniagent import build_model, get_settings

    s = get_settings()
    model = build_model(s)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == s.model
    assert str(model.openai_api_base) == s.base_url


def test_build_model_temperature_override() -> None:
    from omniagent import build_model, get_settings

    model = build_model(get_settings(), temperature=0.42)
    assert model.temperature == pytest.approx(0.42)


# ————————————————————————— 中间件 / 审核 —————————————————————————


def test_build_middleware_default() -> None:
    from omniagent import build_middleware, get_settings

    mw = build_middleware(_resolved(), get_settings(), workspace_root=".")
    names = {type(m).__name__ for m in mw}
    assert "ModelRetryMiddleware" in names
    assert "ToolRetryMiddleware" in names
    assert "ContextEditingMiddleware" in names


def test_build_middleware_steps_limit() -> None:
    from omniagent import build_middleware, get_settings

    mw = build_middleware(_resolved(steps=30), get_settings(), workspace_root=".")
    assert "ModelCallLimitMiddleware" in {type(m).__name__ for m in mw}


def test_rubric_seed_middleware_injects() -> None:
    from omniagent.review import RubricSeedMiddleware

    mw = RubricSeedMiddleware("RUBRIC")
    assert mw.before_agent({}, None) == {"rubric": "RUBRIC"}  # type: ignore[arg-type]
    assert mw.before_agent({"rubric": "x"}, None) is None  # type: ignore[arg-type]


def test_build_review_middleware() -> None:
    from deepagents.middleware.rubric import RubricMiddleware

    from omniagent import build_model, get_settings
    from omniagent.review import RubricSeedMiddleware, build_review_middleware

    model = build_model(get_settings())
    pipe = build_review_middleware(
        _resolved(mode="pipeline", review={"rubric": "x"}), model
    )
    assert [type(m) for m in pipe] == [RubricSeedMiddleware, RubricMiddleware]
    assert build_review_middleware(_resolved(mode="react"), model) == []  # 无审核
    assert build_review_middleware(_resolved(mode="pipeline"), model) == []  # 缺 rubric


# ————————————————————————— 工作区 / MCP —————————————————————————


def test_init_workspace_mkdir() -> None:
    from omniagent import get_settings, init_workspace

    root = init_workspace(get_settings().workspace)
    assert root.is_dir()


def test_load_mcp_tools_empty() -> None:
    from omniagent import load_mcp_tools

    assert asyncio.run(load_mcp_tools({})) == []


# ————————————————————————— agent 组装(builder) —————————————————————————


def test_build_agent_constructs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import build_agent

    agent = build_agent(
        resolved=_resolved(), skill_sources=[], workspace=str(tmp_path / "ws")
    )
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "astream")
    # 纯 Aegra 形态:持久化交给平台,图本身不带 checkpointer / store。
    assert agent.checkpointer is None
    assert agent.store is None


def test_build_agent_exposes_default_tools(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """默认(react)有跨平台 execute + 文件工具。"""
    from omniagent import build_agent

    agent = build_agent(
        resolved=_resolved(), skill_sources=[], workspace=str(tmp_path / "ws")
    )
    registered = {
        t.name
        for t in agent.nodes["tools"].bound._tools_by_name.values()  # type: ignore[attr-defined]
    }
    assert "execute" in registered
    assert {"read_file", "write_file", "edit_file", "glob", "grep"} <= registered


def test_backend_selection_by_execute(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """execute 未裁剪 → LocalShellBackend;裁剪(bash:false)→ FilesystemBackend。"""
    from deepagents.backends import FilesystemBackend, LocalShellBackend

    from omniagent.builder import _backend

    assert isinstance(_backend(_resolved(), tmp_path), LocalShellBackend)
    nb = _backend(_resolved(tools={"bash": False}), tmp_path)
    assert isinstance(nb, FilesystemBackend)
    assert not isinstance(nb, LocalShellBackend)


def test_tool_filter() -> None:
    """ToolFilter 从模型请求移除被裁剪的工具。"""
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

    g = asyncio.run(graph())
    assert hasattr(g, "invoke")
    assert hasattr(g, "astream")
    assert g.checkpointer is None  # Aegra 注入 Postgres 持久化


def test_graph_resolve_scope() -> None:
    """工厂图按 (user, tenant, agent) 解析;无鉴权时回退 configurable。"""
    from omniagent.graph import _resolve_scope

    cfg = {"configurable": {"user_id": "u1", "tenant": "t1", "agent": "a1"}}
    assert _resolve_scope(cfg) == ("u1", "t1", "a1")


def test_graph_rejects_bad_agent() -> None:
    """工厂图对穿越式 agent 直接拒绝(防写到别处)。"""
    from omniagent.graph import graph

    with pytest.raises(ValueError):  # noqa: PT011
        asyncio.run(graph({"configurable": {"agent": "../escape"}}))


def test_graph_caches_per_scope_and_config() -> None:
    """同 (scope, 配置指纹) 复用图;不同 agent / 用户 / 租户 / mode 各自独立。"""
    from omniagent.graph import graph

    base = {"user_id": "u1", "tenant": "t1", "agent": "a1"}

    async def run() -> tuple[object, ...]:
        g1 = await graph({"configurable": base})
        same = await graph({"configurable": dict(base)})
        diff_agent = await graph({"configurable": {**base, "agent": "a2"}})
        diff_user = await graph({"configurable": {**base, "user_id": "u2"}})
        diff_tenant = await graph({"configurable": {**base, "tenant": "t2"}})
        diff_mode = await graph(
            {"configurable": {**base, "mode": "pipeline", "review": {"rubric": "x"}}}
        )
        return g1, same, diff_agent, diff_user, diff_tenant, diff_mode

    g1, same, diff_agent, diff_user, diff_tenant, diff_mode = asyncio.run(run())
    assert same is g1
    assert diff_agent is not g1
    assert diff_user is not g1
    assert diff_tenant is not g1
    assert diff_mode is not g1


def test_resolve_scope_from_auth_user() -> None:
    """鉴权 ``User``:identity→user、tenant→tenant;客户端 configurable 不可伪造。"""
    auth = pytest.importorskip("aegra_api.models.auth")
    user_cls = auth.User
    from omniagent.graph import _resolve_scope

    def scope(user: object, **extra: object) -> tuple[str, str, str]:
        cfg = {"configurable": {"agent": "a1", "langgraph_auth_user": user, **extra}}
        return _resolve_scope(cfg)

    assert scope(user_cls(identity="alice", tenant="acme")) == ("alice", "acme", "a1")
    assert scope(user_cls(identity="bob"))[1] == "public"  # 无 tenant -> public
    # 防伪造:有鉴权身份时,客户端 configurable.user_id / tenant 被忽略
    u, t, _a = scope(user_cls(identity="real", tenant="realt"), user_id="x", tenant="y")
    assert (u, t) == ("real", "realt")


# ————————————————————————— auth(内网,无 ServiceKey) —————————————————————————


def test_auth_resolve_identity() -> None:
    """内网信任:直接读 X-User-Id / X-Tenant-Id;缺失回退匿名 public。"""
    from omniagent.auth import resolve_identity

    out = resolve_identity({"x-user-id": "alice", "x-tenant-id": "acme"})
    assert out == {"identity": "alice", "tenant": "acme"}
    assert resolve_identity({}) == {"identity": "anonymous", "tenant": "public"}


# ————————————————————————— skill / 多租户 —————————————————————————


def test_skill_sources(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """返回 [<tenant>/<agent>](每个 agent 独立);目录自动创建,无全局公有。"""
    from pathlib import Path

    from omniagent.workspace import skill_sources

    (agent_dir,) = skill_sources(tmp_path / "skl", "t1", "a1")
    assert Path(agent_dir).is_dir() and agent_dir.endswith("/t1/a1")


def test_skill_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """save / list / delete per-agent skill(含多文件脚本)。"""
    from omniagent import delete_skill, list_skills, save_skill

    root = tmp_path / "skl"
    save_skill(
        root,
        "t1",
        "a1",
        "my",
        {"SKILL.md": "---\nname: my\ndescription: d\n---\n", "scripts/run.py": "x=1"},
    )
    assert "my" in list_skills(root, "t1", "a1")
    assert (root / "t1" / "a1" / "my" / "scripts" / "run.py").is_file()
    assert delete_skill(root, "t1", "a1", "my") is True
    assert "my" not in list_skills(root, "t1", "a1")


def test_skill_rejects_traversal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import save_skill

    with pytest.raises(ValueError):  # noqa: PT011 - 名称穿越
        save_skill(tmp_path, "t1", "a1", "../evil", {"SKILL.md": "x"})
    with pytest.raises(ValueError):  # noqa: PT011 - 文件路径穿越
        save_skill(tmp_path, "t1", "a1", "ok", {"../evil.py": "x"})
    with pytest.raises(ValueError):  # noqa: PT011 - 缺 SKILL.md
        save_skill(tmp_path, "t1", "a1", "ok", {"a.txt": "x"})


def test_safe_segment_rejects_traversal() -> None:
    from omniagent.config import safe_segment

    assert safe_segment("ok") == "ok"
    for bad in ("", ".", "..", "a/b", "a\\b"):
        with pytest.raises(ValueError):  # noqa: PT011
            safe_segment(bad)


def test_purge_agent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """purge 清该 agent 的 skill + 所有用户的工作目录;返回各部分是否删除。"""
    from omniagent import purge_agent, save_skill

    skl, ws = tmp_path / "skl", tmp_path / "ws"
    save_skill(
        skl, "t1", "a1", "s", {"SKILL.md": "---\nname: s\ndescription: d\n---\n"}
    )
    (ws / "work" / "t1" / "u1" / "a1").mkdir(parents=True)
    (ws / "work" / "t1" / "u2" / "a1").mkdir(parents=True)
    assert purge_agent(skl, ws, "t1", "a1") == {"skills": True, "work": True}
    assert not (skl / "t1" / "a1").exists()
    assert not (ws / "work" / "t1" / "u1" / "a1").exists()
    assert purge_agent(skl, ws, "t1", "a1") == {"skills": False, "work": False}


def test_http_routes() -> None:
    """skill CRUD + agent 清理路由;agent 记录用 Aegra 原生 /assistants。"""
    pytest.importorskip("fastapi")
    pytest.importorskip("aegra_api")
    from omniagent.http import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/skills", "/skills/{name}", "/agents/{agent}"} <= paths
