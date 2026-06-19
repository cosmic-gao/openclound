"""构造级冒烟测试:验证包可导入、各层可构建、agent 可编译,不真正调用模型。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """每个用例使用独立的临时工作区与占位密钥,避免网络与污染 cwd。"""
    # 切到干净的临时目录,确保不受仓库内开发者本地 .env 影响(测试可重现)。
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("AGENT_SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-placeholder")
    # 清掉可能干扰默认值的环境变量(OPENAI_BASE_URL 清掉以测内置默认网关)。
    for var in (
        "AGENT_ENABLE_SHELL",
        "AGENT_ENABLE_HITL",
        "AGENT_MODEL",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    # 清空工厂图缓存,避免跨用例(各自 tmp 目录)命中陈旧编译图。
    import omniagent.graph as _graph

    _graph._build_agent.cache_clear()


# ————————————————————————— 包元数据 / 导出 —————————————————————————


def test_package_metadata() -> None:
    import omniagent

    assert omniagent.__version__ == "0.1.0"
    assert callable(omniagent.build_agent)
    assert callable(omniagent.build_async_agent)
    # 关键公共 API 都在 __all__ 中
    for name in (
        "build_agent",
        "build_async_agent",
        "build_model",
        "build_middleware",
        "get_settings",
        "load_mcp_tools",
        "Settings",
    ):
        assert name in omniagent.__all__


# ————————————————————————— 配置 —————————————————————————


def test_settings_defaults() -> None:
    from omniagent import GATEWAY_BASE_URL, get_settings

    s = get_settings()
    assert s.base_url == GATEWAY_BASE_URL
    assert s.model == "claude-sonnet-4-6"
    assert s.enable_shell is True
    assert s.enable_hitl is False
    assert s.pii_strategy == "off"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from omniagent import get_settings

    monkeypatch.setenv("AGENT_MODEL", "gpt-5.1")
    monkeypatch.setenv("AGENT_ENABLE_SHELL", "0")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.7")
    s = get_settings()
    assert s.model == "gpt-5.1"
    assert s.enable_shell is False
    assert s.temperature == pytest.approx(0.7)


def test_settings_reads_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """get_settings() 经 pydantic-settings 读取 cwd 下的 .env。"""
    from omniagent import get_settings

    monkeypatch.delenv("AGENT_FALLBACK_MODEL", raising=False)
    (tmp_path / ".env").write_text("AGENT_FALLBACK_MODEL=backup\n", encoding="utf-8")
    assert get_settings().fallback_model == "backup"


def test_settings_reads_openai_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """连接走标准 OPENAI_BASE_URL / OPENAI_API_KEY(可指向 MiniMax 等任意端点)。"""
    from omniagent import get_settings

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mm")
    s = get_settings()
    assert s.base_url == "https://api.minimaxi.com/v1"
    assert s.api_key == "sk-test-mm"


# ————————————————————————— 模型 —————————————————————————


def test_build_model_targets_gateway() -> None:
    from langchain_openai import ChatOpenAI

    from omniagent import build_model, get_settings

    s = get_settings()
    model = build_model(s)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == s.model
    assert str(model.openai_api_base) == s.base_url


def test_build_model_backfills_openai_env() -> None:
    """build_model 应把网关回填到 OPENAI_*,使 embeddings 等也走同一网关。"""
    import os

    from omniagent import build_model, get_settings

    s = get_settings()
    build_model(s)
    assert os.environ.get("OPENAI_API_KEY") == s.api_key
    assert os.environ.get("OPENAI_BASE_URL") == s.base_url


# ————————————————————————— 中间件 —————————————————————————


def test_build_middleware_default() -> None:
    from omniagent import build_middleware, get_settings

    mw = build_middleware(get_settings(), workspace_root=".")
    names = {type(m).__name__ for m in mw}
    # 默认:重试 + 上下文管理(shell 由 backend 提供,不在 middleware 里)
    assert "ModelRetryMiddleware" in names
    assert "ToolRetryMiddleware" in names
    assert "ContextEditingMiddleware" in names


def test_build_middleware_respects_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from omniagent import build_middleware, get_settings

    monkeypatch.setenv("AGENT_PII_STRATEGY", "redact")
    monkeypatch.setenv("AGENT_ENABLE_FILE_SEARCH", "1")
    mw = build_middleware(get_settings(), workspace_root=".")
    names = [type(m).__name__ for m in mw]
    assert "PIIMiddleware" in names  # 启用后每种 PII 类型一条
    assert "FilesystemFileSearchMiddleware" in names


def test_interrupts() -> None:
    from omniagent import get_settings, interrupts
    from omniagent.config import get_settings as gs

    assert interrupts(get_settings()) == {}  # hitl off

    s = gs()
    s.enable_hitl = True
    interrupt_on = interrupts(s)
    assert interrupt_on["write_file"] is True
    assert interrupt_on["execute"] is True  # shell 工具名为 execute


# ————————————————————————— 工作区 / skills / memory —————————————————————————


def test_workspace_initializes_templates() -> None:
    from omniagent import get_settings
    from omniagent.workspace import has_skills, init_workspace, memory_files

    root = init_workspace(get_settings().workspace)
    assert root.is_dir()
    assert has_skills(root)
    assert memory_files(root) == ["memories/AGENTS.md"]
    # 示例技能存在
    assert (root / "skills" / "deep-research" / "SKILL.md").is_file()


# ————————————————————————— MCP —————————————————————————


def test_load_mcp_tools_empty() -> None:
    import asyncio

    from omniagent import load_mcp_tools

    assert asyncio.run(load_mcp_tools({})) == []


# ————————————————————————— agent 组装 —————————————————————————


def test_build_agent_constructs() -> None:
    from omniagent import build_agent

    agent = build_agent()
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "astream")


def test_build_agent_exposes_shell_and_file_tools() -> None:
    """启用 shell 时应有跨平台 execute 工具 + 文件工具。"""
    from omniagent import build_agent

    agent = build_agent()
    registered = {
        t.name
        for t in agent.nodes["tools"].bound._tools_by_name.values()  # type: ignore[attr-defined]
    }
    # execute(LocalShellBackend 提供的跨平台 shell)与文件工具都在
    assert "execute" in registered
    assert {"read_file", "write_file", "edit_file", "glob", "grep"} <= registered


def test_backend_selection_by_shell_flag(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """启用 shell → LocalShellBackend(跨平台);关闭 → 纯 FilesystemBackend。"""
    from deepagents.backends import FilesystemBackend, LocalShellBackend

    from omniagent.builder import _build_backend
    from omniagent.config import get_settings

    s = get_settings()
    s.enable_shell = True
    assert isinstance(_build_backend(s, tmp_path), LocalShellBackend)

    s.enable_shell = False
    backend = _build_backend(s, tmp_path)
    assert isinstance(backend, FilesystemBackend)
    assert not isinstance(backend, LocalShellBackend)


def test_build_agent_with_managed_checkpointer() -> None:
    from omniagent import build_agent

    agent = build_agent(managed_checkpointer=True)
    assert agent.checkpointer is not None


# ————————————————————————— Aegra 部署 —————————————————————————


def test_platform_managed_omits_checkpointer(monkeypatch: pytest.MonkeyPatch) -> None:
    """platform_managed=True 时不带 checkpointer(交给 Aegra),即便开了 HITL。"""
    from omniagent import build_agent

    monkeypatch.setenv("AGENT_ENABLE_HITL", "1")
    # 非平台模式:HITL 会自动补一个进程内 checkpointer。
    assert build_agent().checkpointer is not None
    # 平台模式:持久化交给 Aegra,图本身不带 checkpointer / store。
    platform_agent = build_agent(platform_managed=True)
    assert platform_agent.checkpointer is None
    assert platform_agent.store is None


def test_aegra_graph_factory() -> None:
    """omniagent.graph:graph 应是 Aegra 可加载的 0 参工厂,产出无 checkpointer 的图。"""
    from omniagent.graph import graph

    g = graph()
    assert hasattr(g, "invoke")
    assert hasattr(g, "astream")
    assert g.checkpointer is None  # Aegra 注入 Postgres 持久化


# ————————————————————————— 多租户 / skill —————————————————————————


def test_tenant_skill_sources(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """返回 [公有, 私有];公有从 _data 初始化,私有目录自动创建。"""
    from pathlib import Path

    from omniagent.workspace import tenant_skill_sources

    pub, priv = tenant_skill_sources(tmp_path / "skl", "t1", "a1")
    assert pub.endswith("/public")
    assert (Path(pub) / "deep-research" / "SKILL.md").is_file()  # 公有已 seed
    assert Path(priv).is_dir()  # 私有已建


def test_skill_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """save / list / delete 私有 skill(含多文件脚本)。"""
    from omniagent import delete_skill, list_skills, save_skill

    root = tmp_path / "skl"
    save_skill(
        root,
        "t1",
        "a1",
        "my",
        {"SKILL.md": "---\nname: my\ndescription: d\n---\n", "scripts/run.py": "x=1"},
    )
    assert "my" in list_skills(root, "t1", "a1")["private"]
    assert (root / "t1" / "a1" / "my" / "scripts" / "run.py").is_file()
    assert delete_skill(root, "t1", "a1", "my") is True
    assert "my" not in list_skills(root, "t1", "a1")["private"]


def test_skill_rejects_traversal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from omniagent import save_skill

    with pytest.raises(ValueError):  # noqa: PT011 - 名称穿越
        save_skill(tmp_path, "t1", "a1", "../evil", {"SKILL.md": "x"})
    with pytest.raises(ValueError):  # noqa: PT011 - 文件路径穿越
        save_skill(tmp_path, "t1", "a1", "ok", {"../evil.py": "x"})
    with pytest.raises(ValueError):  # noqa: PT011 - 缺 SKILL.md
        save_skill(tmp_path, "t1", "a1", "ok", {"a.txt": "x"})


def test_graph_factory_per_tenant_agent() -> None:
    """工厂图按 (tenant, agent) 装配;无鉴权时租户回退 configurable.tenant_id。"""
    from omniagent.graph import _resolve_tenant_agent, graph

    cfg = {
        "configurable": {"tenant_id": "t1", "agent_id": "a1", "system_prompt": "scene"}
    }
    assert _resolve_tenant_agent(cfg) == ("t1", "a1", "scene")
    g = graph(cfg)
    assert hasattr(g, "astream")
    assert g.checkpointer is None  # 平台托管持久化


def test_build_agent_with_skill_sources(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """显式 skill_sources(绝对路径)可构建,且不污染/不 seed 工作区。"""
    from omniagent import build_agent

    skl = tmp_path / "src_skills" / "demo"
    skl.mkdir(parents=True)
    (skl / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\nx", encoding="utf-8"
    )
    agent = build_agent(skill_sources=[str(tmp_path / "src_skills")])
    assert hasattr(agent, "astream")


def test_safe_segment_rejects_traversal() -> None:
    """租户 / agent / skill 名做路径穿越校验。"""
    from omniagent.config import safe_segment

    assert safe_segment("ok") == "ok"
    for bad in ("", ".", "..", "a/b", "a\\b"):
        with pytest.raises(ValueError):  # noqa: PT011
            safe_segment(bad)


def test_graph_rejects_bad_agent() -> None:
    """工厂图对穿越式 agent_id 直接拒绝(防写到别处)。"""
    from omniagent.graph import graph

    with pytest.raises(ValueError):  # noqa: PT011
        graph({"configurable": {"agent_id": "../escape"}})


def test_resolve_tenant_from_auth_user() -> None:
    """租户取自鉴权 ``User`` 对象(无 ``.get``):tenant_id 优先、org_id 回退、皆缺
    -> public;且客户端 configurable.tenant_id 不能伪造(有鉴权身份时被忽略)。"""
    auth = pytest.importorskip("aegra_api.models.auth")
    user_cls = auth.User
    from omniagent.graph import _resolve_tenant_agent

    def tenant_of(user: object, **extra: object) -> str:
        cfg = {"configurable": {"agent_id": "a1", "langgraph_auth_user": user, **extra}}
        return _resolve_tenant_agent(cfg)[0]

    # tenant_id 为 extra 字段;org_id 为一等字段(回退);均缺失 -> public
    assert tenant_of(user_cls(identity="u1", tenant_id="t1")) == "t1"
    assert tenant_of(user_cls(identity="u1", org_id="o1")) == "o1"
    assert tenant_of(user_cls(identity="u1", tenant_id="t1", org_id="o1")) == "t1"
    assert tenant_of(user_cls(identity="u1")) == "public"
    # 防伪造:有鉴权身份时,客户端 configurable.tenant_id 被忽略
    spoof = user_cls(identity="u1", tenant_id="real")
    assert tenant_of(spoof, tenant_id="attacker") == "real"


def test_purge_agent_cascades(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """purge 清理私有 skill / 工作目录(Aegra 删 assistant 记录,我方清文件)。"""
    from omniagent import purge_agent, save_skill

    skl, ws = tmp_path / "skl", tmp_path / "ws"
    md = "---\nname: s\ndescription: d\n---\n"
    save_skill(skl, "t1", "a1", "s", {"SKILL.md": md})
    (ws / "work" / "t1" / "a1").mkdir(parents=True)
    assert purge_agent(skl, ws, "t1", "a1") == {"skills": True, "work": True}
    assert not (skl / "t1" / "a1").exists()
    assert not (ws / "work" / "t1" / "a1").exists()
    assert purge_agent(skl, ws, "t1", "a1") == {"skills": False, "work": False}


def test_graph_caches_per_agent() -> None:
    """同 (租户, agent, system_prompt) 复用编译图;不同 agent 各自独立。"""
    from omniagent.graph import graph

    g1 = graph({"configurable": {"tenant_id": "t1", "agent_id": "a1"}})
    g2 = graph({"configurable": {"tenant_id": "t1", "agent_id": "a1"}})
    assert g1 is g2
    assert graph({"configurable": {"tenant_id": "t1", "agent_id": "a2"}}) is not g1


def test_http_routes() -> None:
    """只暴露 Aegra 没有的 skill CRUD;agent 列表/删除/状态用 Aegra 原生 /assistants。"""
    pytest.importorskip("fastapi")
    from omniagent.http import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/skills", "/skills/{name}"} <= paths
    assert not any(p and p.startswith("/agents") for p in paths)  # 不重复 Aegra
