"""openclound ``deepagent`` 基础包。

封装 LangChain ``deepagents``,提供一个集成了 **model(litellm 网关)/ tools /
MCP / skills / memory / middleware(健壮性 + 安全 + shell / 文件操作能力)**
的深度智能体构建入口。

快速上手::

    from deepagent import build_agent

    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": "调研 LangGraph"}]})
    print(result["messages"][-1].content)

或使用交互式 CLI(类 Claude Code)::

    deepagent              # 进入 REPL
    deepagent "帮我重构 foo.py"   # 单次任务
"""

from deepagent.agent import (
    DEFAULT_AGENT_NAME,
    DEFAULT_SYSTEM_PROMPT,
    build_agent,
    build_async_agent,
)
from deepagent.config import (
    GATEWAY_BASE_URL,
    PIIStrategy,
    Settings,
    get_settings,
    resolve_workspace,
)
from deepagent.mcp import load_mcp_tools
from deepagent.memory import build_checkpointer, build_store
from deepagent.middleware import build_middleware, high_risk_interrupts
from deepagent.model import build_model
from deepagent.tools import default_tools
from deepagent.workspace import ensure_workspace

__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_SYSTEM_PROMPT",
    "GATEWAY_BASE_URL",
    "PIIStrategy",
    "Settings",
    "build_agent",
    "build_async_agent",
    "build_checkpointer",
    "build_middleware",
    "build_model",
    "build_store",
    "default_tools",
    "ensure_workspace",
    "get_settings",
    "high_risk_interrupts",
    "load_mcp_tools",
    "resolve_workspace",
]
__version__ = "0.1.0"
