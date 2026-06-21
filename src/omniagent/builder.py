"""按 ``ResolvedConfig`` 组装 deep agent(平台托管:无 checkpointer / store)。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from deepagents import create_deep_agent

from omniagent.config import Settings, get_settings
from omniagent.memory import build_backend, memory_sources
from omniagent.middleware import ToolFilter, build_middleware, build_review_middleware
from omniagent.model import build_model
from omniagent.storage import init_workspace

if TYPE_CHECKING:
    from pathlib import Path

    from langchain.agents.middleware import AgentMiddleware, InterruptOnConfig
    from langchain_core.tools import BaseTool

    from omniagent.spec import ResolvedConfig

AGENT_NAME = "openclound-omniagent"


def build_agent(
    *,
    resolved: ResolvedConfig,
    workspace: str | Path,
    skill_sources: list[str],
    agent: str,
    settings: Settings | None = None,
    tools: list[BaseTool] | None = None,
) -> Any:
    """按 :class:`ResolvedConfig` 组装 deep agent;``agent`` 用于记忆命名空间隔离。"""
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
