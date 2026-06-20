"""按 :class:`~omniagent.modes.ResolvedConfig` 组装 deep agent。

纯 Aegra 形态:持久层由平台注入(无 checkpointer / store)。模型、工具裁剪、HITL、审核、
skill、工作区由 per-agent 配置驱动;MCP 工具在 graph 内联加载后传入。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend
from langchain.agents.middleware import AgentMiddleware

from omniagent.config import Settings, get_settings
from omniagent.middleware import build_middleware
from omniagent.model import build_model
from omniagent.review import build_review_middleware
from omniagent.workspace import init_workspace

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from langchain.agents.middleware import (
        InterruptOnConfig,
        ModelRequest,
        ModelResponse,
    )
    from langchain_core.tools import BaseTool

    from omniagent.modes import ResolvedConfig

AGENT_NAME = "openclound-omniagent"


def _tool_name(tool: BaseTool | dict[str, Any]) -> str | None:
    return tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)


class ToolFilter(AgentMiddleware[Any, Any, Any]):
    """从模型请求移除被裁剪的工具(``permission=deny`` / ``tools=false``)。

    deepagents 无 per-agent 工具裁剪的公开参数(仅 HarnessProfile 级),故在请求层过滤;
    须排在注入工具的中间件之后(builder 末尾追加)。
    """

    def __init__(self, excluded: set[str]) -> None:
        super().__init__()
        self._excluded = excluded

    def _filter(self, request: ModelRequest[Any]) -> ModelRequest[Any]:
        kept = [t for t in request.tools if _tool_name(t) not in self._excluded]
        return request.override(tools=kept)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        return handler(self._filter(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        return await handler(self._filter(request))


def _backend(
    resolved: ResolvedConfig, root: Path
) -> FilesystemBackend | LocalShellBackend:
    """``execute`` 未裁剪用跨平台 shell backend,否则纯文件 backend(均 ``virtual_mode``:
    文件工具沙箱化到工作区,跨平台用 ``/`` 虚拟路径)。"""
    if "execute" in resolved.excluded_tools:
        return FilesystemBackend(root_dir=root, virtual_mode=True)
    return LocalShellBackend(root_dir=root, virtual_mode=True, inherit_env=True)


def build_agent(
    *,
    resolved: ResolvedConfig,
    workspace: str | Path,
    skill_sources: list[str],
    settings: Settings | None = None,
    tools: list[BaseTool] | None = None,
    name: str = AGENT_NAME,
) -> Any:
    """按 :class:`ResolvedConfig` 构建 deep agent(平台托管:无 checkpointer / store)。

    Args:
        resolved: 合并后的开关(模型 / 提示 / 工具裁剪 / HITL / 审核)。
        workspace: 该 assistant 的 backend root(``tenant-<id>/assistant-<id>``,虚拟根)。
        skill_sources: skill 虚拟源(如 ``["/skills"]``,无则 ``[]``)。
        settings: 进程级配置;为空则取默认。
        tools: 额外工具(如 :mod:`omniagent.graph` 加载的 MCP 工具)。
        name: agent 名称。
    """
    settings = settings or get_settings()
    root = init_workspace(workspace)
    model = build_model(
        settings, model=resolved.model, temperature=resolved.temperature
    )

    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        *build_middleware(resolved, settings, workspace_root=root),
        *build_review_middleware(resolved, model),
    ]
    if resolved.excluded_tools:
        middleware.append(ToolFilter(set(resolved.excluded_tools)))

    return create_deep_agent(
        model=model,
        tools=list(tools or []),
        system_prompt=resolved.prompt,
        middleware=middleware,
        skills=skill_sources or None,
        backend=_backend(resolved, root),
        interrupt_on=cast(
            "dict[str, bool | InterruptOnConfig] | None",
            resolved.interrupt_on or None,
        ),
        checkpointer=None,  # 持久层由 Aegra 注入
        store=None,
        name=name,
    )
