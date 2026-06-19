"""middleware 全家桶:健壮性 + 上下文管理 + 安全(PII) + 文件搜索。

基于 ``langchain.agents.middleware``(随 deepagents 0.6.11 / langchain 1.3.x 提供),
在 ``create_deep_agent`` 内置中间件(规划 / 文件系统 / 子代理 / 摘要 / 缓存)之外,
按需追加下列能力。注意:``create_deep_agent`` 会把这里返回的中间件插在内置
**基础栈之后、收尾栈之前**(见其 docstring 的 middleware 顺序说明)。

shell 能力不在这里:它由 backend 提供(``LocalShellBackend`` 的跨平台 ``execute``
工具,见 :mod:`omniagent.builder`),而非 bash-only 的 ``ShellToolMiddleware``。

HITL(高危操作人工确认)走 ``create_deep_agent`` 原生的 ``interrupt_on`` 参数
(见 :func:`interrupts`),而非作为一条 middleware。
"""

from __future__ import annotations

from pathlib import Path
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

from omniagent.config import Settings, get_settings
from omniagent.model import build_model

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentMiddleware, InterruptOnConfig

#: 启用 PII 中间件时覆盖的内置类型(刻意排除 ``url`` 之外的常见敏感信息)。
#: ``url`` 在编码场景中误伤率高,默认不纳入。
_PII_TYPES = ("email", "credit_card", "ip", "mac_address")


def build_middleware(
    settings: Settings | None = None,
    *,
    workspace_root: str | Path,
) -> list[AgentMiddleware[Any, Any, Any]]:
    """按配置组装追加 middleware 列表(交给 ``create_deep_agent(middleware=...)``)。

    顺序:健壮性(重试 / 调用上限 / 回退) → 上下文管理 → PII → 文件搜索。

    Args:
        settings: 运行配置;为空则调用 :func:`~omniagent.config.get_settings`。
        workspace_root: 已就绪的工作区绝对路径,用作文件搜索的根。

    Returns:
        中间件实例列表(可能为空)。
    """
    settings = settings or get_settings()
    root = str(workspace_root)
    middleware: list[AgentMiddleware[Any, Any, Any]] = []

    # —— 健壮性:模型 / 工具自动重试 ——
    if settings.model_max_retries > 0:
        middleware.append(ModelRetryMiddleware(max_retries=settings.model_max_retries))
    if settings.tool_max_retries > 0:
        middleware.append(ToolRetryMiddleware(max_retries=settings.tool_max_retries))

    # —— 健壮性:单次运行的调用上限(防失控) ——
    if settings.model_call_limit is not None:
        middleware.append(
            ModelCallLimitMiddleware(
                run_limit=settings.model_call_limit, exit_behavior="end"
            )
        )
    if settings.tool_call_limit is not None:
        middleware.append(
            ToolCallLimitMiddleware(
                run_limit=settings.tool_call_limit, exit_behavior="continue"
            )
        )

    # —— 健壮性:主模型失败时回退到备用模型 ——
    if settings.fallback_model:
        middleware.append(
            ModelFallbackMiddleware(
                build_model(settings, model=settings.fallback_model)
            )
        )

    # —— 上下文管理:清理过旧的工具输出,控制上下文膨胀 ——
    # (会话摘要由 deepagents 内置的 SummarizationMiddleware 负责,此处不重复添加。)
    if settings.context_edit_trigger_tokens > 0:
        middleware.append(
            ContextEditingMiddleware(
                edits=[ClearToolUsesEdit(trigger=settings.context_edit_trigger_tokens)]
            )
        )

    # —— 安全:PII 脱敏(默认 off) ——
    if settings.pii_strategy != "off":
        for pii_type in _PII_TYPES:
            middleware.append(
                PIIMiddleware(
                    pii_type,
                    strategy=settings.pii_strategy,
                    apply_to_input=True,
                    apply_to_tool_results=True,
                )
            )

    # —— 能力:ripgrep 文件搜索(deepagents 已提供 glob/grep,此项默认关闭) ——
    if settings.enable_file_search:
        middleware.append(FilesystemFileSearchMiddleware(root_path=root))

    return middleware


def interrupts(
    settings: Settings | None = None,
) -> dict[str, bool | InterruptOnConfig]:
    """高危工具的 HITL 配置(交给 ``create_deep_agent(interrupt_on=...)``)。

    对写文件 / 编辑文件 / execute(shell)等"会改变外部状态"的工具,在执行前请求
    人工确认。``enable_hitl=False`` 时返回空 dict(不拦截)。

    注意:HITL 依赖 checkpointer 才能中断 / 恢复,因此启用时应配合
    ``build_agent(managed_checkpointer=True)`` 或自带 checkpointer。
    """
    settings = settings or get_settings()
    if not settings.enable_hitl:
        return {}

    interrupt_on: dict[str, bool | InterruptOnConfig] = {
        "write_file": True,
        "edit_file": True,
    }
    # shell 由 LocalShellBackend 的 execute 工具提供(仅 enable_shell 时存在)。
    if settings.enable_shell:
        interrupt_on["execute"] = True
    return interrupt_on
