"""agent 中间件:自定义中间件(ToolFilter / RubricSeedMiddleware)+ 健壮性 / 审核装配。

build_middleware:重试/上限/回退/上下文清理/PII/文件搜索;build_review_middleware:审核。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NotRequired

from deepagents.middleware.rubric import RubricMiddleware
from langchain.agents.middleware import (
    AgentMiddleware,
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    FilesystemFileSearchMiddleware,
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    PIIMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.middleware.types import AgentState

from agentos.model import build_model

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from langchain.agents.middleware import ModelRequest, ModelResponse
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool
    from langgraph.runtime import Runtime

    from agentos.config import Settings
    from agentos.spec import ResolvedConfig

_PII_TYPES = ("email", "credit_card", "ip", "mac_address")  # url 误伤率高,不纳入


def _tool_name(tool: BaseTool | dict[str, Any]) -> str | None:
    return tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)


class ToolFilter(AgentMiddleware[Any, Any, Any]):
    """请求层移除被裁剪的工具;须排在注入工具的中间件之后。"""

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


class _RubricState(AgentState):
    rubric: NotRequired[str]


class RubricSeedMiddleware(AgentMiddleware[_RubricState, Any, Any]):
    """把 config 的 rubric 注入 state,供 ``RubricMiddleware`` 读取(须排在其前)。"""

    state_schema = _RubricState

    def __init__(self, rubric: str) -> None:
        super().__init__()
        self._rubric = rubric

    def before_agent(
        self, state: _RubricState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return None if state.get("rubric") else {"rubric": self._rubric}

    async def abefore_agent(
        self, state: _RubricState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return None if state.get("rubric") else {"rubric": self._rubric}


def build_review_middleware(
    resolved: ResolvedConfig, grader_model: BaseChatModel
) -> list[AgentMiddleware[Any, Any, Any]]:
    """启用且有 rubric 时返回 ``[seed, RubricMiddleware]``,否则 ``[]``。"""
    if not (resolved.review_enabled and resolved.rubric):
        return []
    return [
        RubricSeedMiddleware(resolved.rubric),
        RubricMiddleware(
            model=grader_model, max_iterations=resolved.review_max_iterations
        ),
    ]


def build_middleware(
    resolved: ResolvedConfig, settings: Settings, *, workspace_root: str | Path
) -> list[AgentMiddleware[Any, Any, Any]]:
    """健壮性(重试 / 上限 / 回退)→ 上下文清理 → PII → 文件搜索。"""
    mw: list[AgentMiddleware[Any, Any, Any]] = []
    if settings.model_max_retries > 0:
        mw.append(ModelRetryMiddleware(max_retries=settings.model_max_retries))
    if settings.tool_max_retries > 0:
        mw.append(ToolRetryMiddleware(max_retries=settings.tool_max_retries))
    if resolved.steps is not None:
        mw.append(
            ModelCallLimitMiddleware(run_limit=resolved.steps, exit_behavior="end")
        )
    if settings.tool_call_limit is not None:
        mw.append(
            ToolCallLimitMiddleware(
                run_limit=settings.tool_call_limit, exit_behavior="continue"
            )
        )
    if resolved.fallback_model:
        mw.append(
            ModelFallbackMiddleware(
                build_model(
                    model=resolved.fallback_model,
                    base_url=resolved.base_url,
                    api_key=resolved.api_key,
                    max_retries=settings.model_max_retries,
                )
            )
        )
    if settings.context_edit_trigger_tokens > 0:
        mw.append(
            ContextEditingMiddleware(
                edits=[ClearToolUsesEdit(trigger=settings.context_edit_trigger_tokens)]
            )
        )
    if resolved.pii_strategy != "off":
        mw.extend(
            PIIMiddleware(
                t,
                strategy=resolved.pii_strategy,
                apply_to_input=True,
                apply_to_tool_results=True,
            )
            for t in _PII_TYPES
        )
    if resolved.enable_file_search:
        mw.append(FilesystemFileSearchMiddleware(root_path=str(workspace_root)))
    return mw
