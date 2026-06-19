"""openclound ``deepagent`` 基础包。

封装 LangChain ``deepagents``,提供一个集成了 **model(OpenAI 兼容网关)/ MCP /
skills / memory / middleware(健壮性 + 安全 + shell / 文件操作能力)** 的深度智能体
构建入口,并可作为 Aegra 项目部署。

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
    export_openai_env,
    get_settings,
    resolve_path,
)
from deepagent.mcp import load_mcp_tools
from deepagent.middleware import build_middleware, interrupts
from deepagent.model import build_model
from deepagent.workspace import init_workspace

__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_SYSTEM_PROMPT",
    "GATEWAY_BASE_URL",
    "PIIStrategy",
    "Settings",
    "build_agent",
    "build_async_agent",
    "build_middleware",
    "build_model",
    "export_openai_env",
    "get_settings",
    "init_workspace",
    "interrupts",
    "load_mcp_tools",
    "resolve_path",
]
__version__ = "0.1.0"
