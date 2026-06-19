"""深度智能体构建入口:组装 model / tools / skills / memory / middleware / subagents。

- **模型**:经 OpenAI 兼容端点接入(见 :mod:`deepagent.model`)。
- **工具**:deepagents 内置工具(规划 / 文件系统 / 子代理 / shell) + 调用方工具
  + (异步入口下)MCP 工具。
- **能力 / 安全**:shell、文件搜索、重试、调用上限、上下文管理、PII、HITL
  (见 :mod:`deepagent.middleware`)。
- **skills**:工作区 ``skills/`` 下每个含 ``SKILL.md`` 的目录(声明式按需加载)。
- **memory**:工作区 ``memories/AGENTS.md`` 注入系统提示 + 可选短期 / 长期记忆。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from deepagent.config import Settings, get_settings
from deepagent.mcp import load_mcp_tools
from deepagent.middleware import build_middleware, interrupts
from deepagent.model import build_model
from deepagent.workspace import has_skills, init_workspace, memory_files

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from deepagents import SubAgent
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.store.base import BaseStore

#: 追加到 deepagents 内置系统提示之前的默认指令(``create_deep_agent`` 会把
#: 调用方 ``system_prompt`` 放在其内置 BASE 提示之前)。
DEFAULT_SYSTEM_PROMPT = (
    "You are openclound's deep agent. Plan with the todo tool, keep working notes "
    "in the file system, consult your skills for domain workflows, and delegate "
    "isolated subtasks to subagents. Be thorough and verify before finishing."
)

#: agent 名称(出现在 LangGraph 元数据 / 追踪中)。
DEFAULT_AGENT_NAME = "openclound-deepagent"


def _build_backend(settings: Settings, root: Path) -> FilesystemBackend:
    """按是否启用 shell 选择 backend(均为真实本地文件系统,``virtual_mode=False``)。

    - 启用 shell:``LocalShellBackend`` —— 用 ``subprocess(shell=True)`` 跨平台执行,
      Windows 走 ``cmd``、POSIX 走 ``/bin/sh``,并暴露内置 ``execute`` 工具;
      ``inherit_env=True`` 让子进程继承 PATH 等环境(``python`` / ``git`` 可用)。
    - 关闭 shell:``FilesystemBackend`` —— 仅文件工具,``execute`` 会被自动过滤。
    """
    if settings.enable_shell:
        return LocalShellBackend(root_dir=root, virtual_mode=False, inherit_env=True)
    return FilesystemBackend(root_dir=root, virtual_mode=False)


def build_agent(
    *,
    tools: list[BaseTool] | None = None,
    subagents: Sequence[SubAgent] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    settings: Settings | None = None,
    model: BaseChatModel | None = None,
    enable_skills: bool = True,
    enable_memory: bool = True,
    managed_checkpointer: bool = False,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    store: BaseStore | None = None,
    platform_managed: bool = False,
    extra_middleware: Sequence[AgentMiddleware] | None = None,
    name: str = DEFAULT_AGENT_NAME,
) -> Any:
    """构建一个集成全部能力的 deep agent(同步)。

    使用 OpenAI 兼容端点模型、deepagents 内置工具 + 调用方工具、skills 与记忆。
    需要 MCP 工具时请改用 :func:`build_async_agent`。

    Args:
        tools: 额外的自定义工具(与 deepagents 内置工具合并)。
        subagents: 子代理配置列表(经 ``task`` 工具调用)。
        system_prompt: 追加到 deepagents 内置系统提示之前的指令。
        settings: 运行配置;为空则调用 :func:`~deepagent.config.get_settings`。
        model: 直接指定模型实例,覆盖 ``settings`` 中的网关模型。
        enable_skills: 是否加载工作区 ``skills/``。
        enable_memory: 是否加载 ``memories/AGENTS.md`` 并注入系统提示。
        managed_checkpointer: ``True`` 时**自动**附带进程内 checkpointer / store
            (短期 + 长期记忆)。也可通过 ``checkpointer`` / ``store`` 显式传入。
        checkpointer: 显式短期记忆;优先于 ``managed_checkpointer`` 自动创建的实例。
        store: 显式长期记忆。
        platform_managed: ``True`` 时由部署平台(如 Aegra / LangGraph Platform)在
            运行时注入 Postgres 持久层,故**不**附带任何 checkpointer / store,也不为
            HITL 自动补 checkpointer(平台的 checkpointer 即可支撑中断 / 恢复)。
            用于 :mod:`deepagent.graph` 暴露给 Aegra 的图工厂。
        extra_middleware: 追加到能力 / 安全中间件之后的自定义中间件。
        name: agent 名称。

    Returns:
        已编译的 LangGraph 图,支持 ``invoke`` / ``ainvoke`` / ``stream`` 等接口。
    """
    settings = settings or get_settings()
    root = init_workspace(settings.workspace)

    llm = model if model is not None else build_model(settings)
    backend = _build_backend(settings, root)

    skills = ["skills"] if enable_skills and has_skills(root) else None
    memory = memory_files(root) if enable_memory else None

    middleware = list(build_middleware(settings, workspace_root=root))
    if extra_middleware:
        middleware.extend(extra_middleware)

    interrupt_on = interrupts(settings)

    if platform_managed:
        # 部署平台(Aegra 等)负责持久化:此处不附带 checkpointer / store。
        checkpointer = None
        store = None
    else:
        if managed_checkpointer:
            checkpointer = checkpointer or InMemorySaver()
            store = store or InMemoryStore()
        # HITL 没有 checkpointer 无法中断 / 恢复 —— 自动补一个进程内 checkpointer。
        if interrupt_on and checkpointer is None:
            checkpointer = InMemorySaver()

    return create_deep_agent(
        model=llm,
        tools=list(tools or []),
        system_prompt=system_prompt,
        middleware=middleware,
        subagents=list(subagents) if subagents else [],
        skills=skills,
        memory=memory,
        backend=backend,
        interrupt_on=interrupt_on or None,
        checkpointer=checkpointer,
        store=store,
        name=name,
    )


async def build_async_agent(
    *,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    tools: list[BaseTool] | None = None,
    **kwargs: Any,
) -> Any:
    """构建一个挂载 MCP 工具的 deep agent(异步)。

    Args:
        mcp_servers: MCP server 连接配置(见 :func:`deepagent.mcp.load_mcp_tools`);
            为空时等价于 :func:`build_agent`。
        tools: 额外的自定义工具(与 MCP 工具、内置工具合并)。
        **kwargs: 透传给 :func:`build_agent`(如 ``subagents`` / ``settings`` 等)。

    Returns:
        已编译的 LangGraph 图。
    """
    mcp_tools = await load_mcp_tools(mcp_servers or {})
    merged: list[BaseTool] = [*(tools or []), *mcp_tools]
    return build_agent(tools=merged, **kwargs)
