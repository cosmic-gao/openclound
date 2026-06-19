"""示例自定义工具。

用 ``@tool`` 装饰器 + 类型注解 + docstring(向模型说明工具用途)。deepagents
会把这些工具与其内置工具(``write_todos`` / 文件系统 / ``task`` 子代理 / shell)
自动合并。这里仅作示范,真实业务工具请在调用方定义后通过 ``tools=`` 传入。
"""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.tools import BaseTool, tool


@tool
def word_count(text: str) -> int:
    """统计文本按空白分隔的词数。

    Args:
        text: 待统计的文本。
    """
    return len(text.split())


@tool
def current_time() -> str:
    """返回当前 UTC 时间(ISO 8601)。"""
    return datetime.now(UTC).isoformat()


def default_tools() -> list[BaseTool]:
    """本包随附的示例工具集合。"""
    return [word_count, current_time]
