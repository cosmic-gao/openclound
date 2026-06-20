"""审核:pipeline 的"审核"步,基于 deepagents ``RubricMiddleware``(自评迭代)。

``RubricMiddleware`` 只从 ``state["rubric"]`` 读 rubric、不接受构造参数,故用
:class:`RubricSeedMiddleware` 把 config 的 rubric 注入运行状态(须排在其前)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NotRequired

from deepagents.middleware.rubric import RubricMiddleware
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.runtime import Runtime

    from omniagent.modes import ResolvedConfig


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
