"""深度智能体(deep agent)的构建入口。

基于 LangChain ``deepagents``:内置任务规划(``write_todos``)、虚拟文件系统、
子代理(``task``)等能力,默认使用 Claude Sonnet 4.6。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent

if TYPE_CHECKING:
    from deepagents import SubAgent

#: 默认模型:Claude Sonnet 4.6(运行时需设置环境变量 ``ANTHROPIC_API_KEY``)。
DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"

#: 追加到 deepagents 内置系统提示之后的默认指令。
DEFAULT_SYSTEM_PROMPT = (
    "You are a capable deep agent. Plan with the todo tool, keep working notes "
    "in the virtual file system, and delegate isolated subtasks to subagents. "
    "Be thorough and verify your work before finishing."
)


def build_agent(
    *,
    tools: list[Any] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    model: str = DEFAULT_MODEL,
    subagents: list[SubAgent] | None = None,
) -> Any:
    """构建并返回一个已编译的 deep agent。

    Args:
        tools: 额外的自定义工具;deepagents 已内置规划 / 文件系统 / 子代理工具。
        system_prompt: 追加到内置系统提示之后的指令。
        model: 模型标识(``provider:model`` 形式),默认 Claude Sonnet 4.6。
        subagents: 子代理配置;每项形如
            ``{"name": ..., "description": ..., "system_prompt": ...}``。

    Returns:
        已编译的 LangGraph 图,支持 ``invoke`` / ``ainvoke`` / ``stream`` 等接口。
    """
    return create_deep_agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        subagents=subagents or [],
    )
