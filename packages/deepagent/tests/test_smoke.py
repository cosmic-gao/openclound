"""构造级冒烟测试:验证包可导入、各层可构建、agent 可编译,不真正调用模型。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """每个用例使用独立的临时工作区与占位密钥,避免网络与污染 cwd。"""
    # 切到干净的临时目录,确保不受仓库内开发者本地 .env 影响(测试可重现)。
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEEPAGENT_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("DEEPAGENT_API_KEY", "sk-placeholder")
    # 清掉可能干扰默认值的环境变量
    for var in ("DEEPAGENT_ENABLE_SHELL", "DEEPAGENT_ENABLE_HITL", "DEEPAGENT_MODEL"):
        monkeypatch.delenv(var, raising=False)


# ————————————————————————— 包元数据 / 导出 —————————————————————————


def test_package_metadata() -> None:
    import deepagent

    assert deepagent.__version__ == "0.1.0"
    assert callable(deepagent.build_agent)
    assert callable(deepagent.build_async_agent)
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
        assert name in deepagent.__all__


# ————————————————————————— 配置 —————————————————————————


def test_settings_defaults() -> None:
    from deepagent import GATEWAY_BASE_URL, get_settings

    s = get_settings()
    assert s.base_url == GATEWAY_BASE_URL
    assert s.model == "claude-sonnet-4-6"
    assert s.enable_shell is True
    assert s.enable_hitl is False
    assert s.pii_strategy == "off"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from deepagent import get_settings

    monkeypatch.setenv("DEEPAGENT_MODEL", "gpt-5.1")
    monkeypatch.setenv("DEEPAGENT_ENABLE_SHELL", "0")
    monkeypatch.setenv("DEEPAGENT_TEMPERATURE", "0.7")
    s = get_settings()
    assert s.model == "gpt-5.1"
    assert s.enable_shell is False
    assert s.temperature == pytest.approx(0.7)


def test_settings_reads_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """get_settings() 应加载 cwd 下的 .env(fixture 已切到 tmp_path)。"""
    import os

    from deepagent import get_settings

    monkeypatch.delenv("DEEPAGENT_FALLBACK_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPAGENT_FALLBACK_MODEL=backup\n", encoding="utf-8")
    try:
        assert get_settings().fallback_model == "backup"
    finally:
        # load_dotenv 直接写 os.environ,monkeypatch 不追踪,手动清理避免泄漏。
        os.environ.pop("DEEPAGENT_FALLBACK_MODEL", None)


# ————————————————————————— 模型 —————————————————————————


def test_build_model_targets_gateway() -> None:
    from langchain_openai import ChatOpenAI

    from deepagent import build_model, get_settings

    s = get_settings()
    model = build_model(s)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == s.model
    assert str(model.openai_api_base) == s.base_url


# ————————————————————————— 中间件 —————————————————————————


def test_build_middleware_default() -> None:
    from deepagent import build_middleware, get_settings

    mw = build_middleware(get_settings(), workspace_root=".")
    names = {type(m).__name__ for m in mw}
    # 默认:重试 + 上下文管理(shell 由 backend 提供,不在 middleware 里)
    assert "ModelRetryMiddleware" in names
    assert "ToolRetryMiddleware" in names
    assert "ContextEditingMiddleware" in names


def test_build_middleware_respects_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from deepagent import build_middleware, get_settings

    monkeypatch.setenv("DEEPAGENT_PII_STRATEGY", "redact")
    monkeypatch.setenv("DEEPAGENT_ENABLE_FILE_SEARCH", "1")
    mw = build_middleware(get_settings(), workspace_root=".")
    names = [type(m).__name__ for m in mw]
    assert "PIIMiddleware" in names  # 启用后每种 PII 类型一条
    assert "FilesystemFileSearchMiddleware" in names


def test_high_risk_interrupts() -> None:
    from deepagent import get_settings, high_risk_interrupts
    from deepagent.config import get_settings as gs

    assert high_risk_interrupts(get_settings()) == {}  # hitl off

    s = gs()
    s.enable_hitl = True
    interrupts = high_risk_interrupts(s)
    assert interrupts["write_file"] is True
    assert interrupts["execute"] is True  # shell 工具名为 execute


# ————————————————————————— 工作区 / skills / memory —————————————————————————


def test_workspace_initializes_templates() -> None:
    from deepagent import get_settings
    from deepagent.workspace import ensure_workspace, has_skills, memory_files

    root = ensure_workspace(get_settings().workspace)
    assert root.is_dir()
    assert has_skills(root)
    assert memory_files(root) == ["memories/AGENTS.md"]
    # 示例技能存在
    assert (root / "skills" / "deep-research" / "SKILL.md").is_file()


# ————————————————————————— 工具 / MCP —————————————————————————


def test_default_tools() -> None:
    from deepagent import default_tools

    tools = default_tools()
    names = {t.name for t in tools}
    assert {"word_count", "current_time"} <= names


def test_load_mcp_tools_empty() -> None:
    import asyncio

    from deepagent import load_mcp_tools

    assert asyncio.run(load_mcp_tools({})) == []


# ————————————————————————— agent 组装 —————————————————————————


def test_build_agent_constructs() -> None:
    from deepagent import build_agent

    agent = build_agent()
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "astream")


def test_build_agent_exposes_shell_and_file_tools() -> None:
    """启用 shell 时应有跨平台 execute 工具 + 文件工具 + 自定义工具。"""
    from deepagent import build_agent

    agent = build_agent()
    registered = {
        t.name
        for t in agent.nodes["tools"].bound._tools_by_name.values()  # type: ignore[attr-defined]
    }
    # execute(LocalShellBackend 提供的跨平台 shell)与文件工具都在
    assert "execute" in registered
    assert {"read_file", "write_file", "edit_file", "glob", "grep"} <= registered
    # 自定义示例工具被合并
    assert "word_count" in registered


def test_backend_selection_by_shell_flag(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """启用 shell → LocalShellBackend(跨平台);关闭 → 纯 FilesystemBackend。"""
    from deepagents.backends import FilesystemBackend, LocalShellBackend

    from deepagent.agent import _build_backend
    from deepagent.config import get_settings

    s = get_settings()
    s.enable_shell = True
    assert isinstance(_build_backend(s, tmp_path), LocalShellBackend)

    s.enable_shell = False
    backend = _build_backend(s, tmp_path)
    assert isinstance(backend, FilesystemBackend)
    assert not isinstance(backend, LocalShellBackend)


def test_build_agent_with_managed_checkpointer() -> None:
    from deepagent import build_agent

    agent = build_agent(managed_checkpointer=True)
    assert agent.checkpointer is not None


# ————————————————————————— CLI 纯函数 —————————————————————————


def test_cli_helpers(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    from deepagent.cli import _load_mcp, _short, _text

    assert _text("hello") == "hello"
    assert _text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    assert _short("x" * 500).endswith("…")
    assert _load_mcp(None) is None

    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"fs": {"transport": "stdio"}}}))
    assert _load_mcp(str(cfg)) == {"fs": {"transport": "stdio"}}
