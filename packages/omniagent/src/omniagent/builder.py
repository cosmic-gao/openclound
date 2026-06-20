"""按 ``ResolvedConfig`` 组装 deep agent(平台托管:无 checkpointer / store)。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware

from omniagent.config import Settings, get_settings
from omniagent.memory import build_backend, memory_sources
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

    from omniagent.resolve import ResolvedConfig

AGENT_NAME = "openclound-omniagent"


def _tool_name(tool: BaseTool | dict[str, Any]) -> str | None:
    return tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)


class ToolFilter(AgentMiddleware[Any, Any, Any]):
    """请求层移除被裁剪的工具(``permission=deny`` / ``tools=false``)。

    deepagents 无公开的工具裁剪参数,故在此过滤(须排在注入工具的中间件之后)。
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


def build_agent(
    *,
    resolved: ResolvedConfig,
    workspace: str | Path,
    skill_sources: list[str],
    agent: str,
    settings: Settings | None = None,
    tools: list[BaseTool] | None = None,
) -> Any:
    """按 :class:`ResolvedConfig` 构建 deep agent(无 checkpointer / store,由平台注入)。

    Args:
        resolved: 合并后的开关。
        workspace: 该 assistant 的 backend root(``<base>/<agent>``)。
        skill_sources: skill 虚拟源(如 ``["/skills"]``)。
        agent: assistant 标识(记忆命名空间隔离)。
        settings: 进程级运行参数;为空则取默认。
        tools: 额外工具(如 MCP)。
    """
    settings = settings or get_settings()
    model = build_model(
        model=resolved.model,
        base_url=resolved.base_url,
        api_key=resolved.api_key,
        temperature=resolved.temperature,
        model_params=resolved.model_params,
        max_retries=settings.model_max_retries,
    )
    root = init_workspace(workspace)
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
        backend=build_backend(resolved, root, agent),
        memory=memory_sources(resolved),
        interrupt_on=cast(
            "dict[str, bool | InterruptOnConfig] | None",
            resolved.interrupt_on or None,
        ),
        checkpointer=None,
        store=None,
        name=AGENT_NAME,
    )
