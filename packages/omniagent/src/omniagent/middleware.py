"""健壮性 / 上下文 / 安全中间件:重试 / 上限 / 回退 / 上下文清理 / PII / 文件搜索。

``create_deep_agent`` 内置之外按需追加;HITL / 工具裁剪 / 审核见 builder 与 review。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import (
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

from omniagent.model import build_model

if TYPE_CHECKING:
    from pathlib import Path

    from langchain.agents.middleware import AgentMiddleware

    from omniagent.config import Settings
    from omniagent.resolve import ResolvedConfig

#: 启用 PII 时覆盖的类型(``url`` 误伤率高,不纳入)。
_PII_TYPES = ("email", "credit_card", "ip", "mac_address")


def build_middleware(
    resolved: ResolvedConfig, settings: Settings, *, workspace_root: str | Path
) -> list[AgentMiddleware[Any, Any, Any]]:
    """组装健壮性(重试 / 上限 / 回退)→ 上下文管理 → PII → 文件搜索。"""
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
