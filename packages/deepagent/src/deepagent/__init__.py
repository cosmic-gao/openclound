"""openclound ``deepagent`` 基础包。

封装 LangChain ``deepagents``,提供构建深度智能体的便捷入口 :func:`build_agent`。
"""

from deepagent.agent import DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT, build_agent

__all__ = ["DEFAULT_MODEL", "DEFAULT_SYSTEM_PROMPT", "build_agent"]
__version__ = "0.1.0"
