"""openclound ``omniagent`` 通用 agent 基础包。

封装 LangChain ``deepagents``,提供一个集成了 **model(OpenAI 兼容端点)/ MCP /
skills / memory / middleware(健壮性 + 安全 + shell / 文件操作能力)** 的 agent
构建入口,作为 **Aegra 项目** 部署(多租户 / 多 Agent,见 ``graph.py``)。

快速上手(库)::

    from omniagent import build_agent

    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": "调研 LangGraph"}]})
    print(result["messages"][-1].content)

部署到 Aegra:``aegra dev``(图入口 ``omniagent.graph:graph``)。
"""

from omniagent.builder import (
    DEFAULT_AGENT_NAME,
    DEFAULT_SYSTEM_PROMPT,
    build_agent,
    build_async_agent,
)
from omniagent.config import (
    GATEWAY_BASE_URL,
    PIIStrategy,
    Settings,
    export_openai_env,
    get_settings,
    resolve_path,
)
from omniagent.mcp import load_mcp_tools
from omniagent.middleware import build_middleware, interrupts
from omniagent.model import build_model
from omniagent.skills import delete_skill, list_skills, save_skill
from omniagent.workspace import (
    init_workspace,
    purge_agent,
    tenant_skill_sources,
)

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
    "delete_skill",
    "export_openai_env",
    "get_settings",
    "init_workspace",
    "interrupts",
    "list_skills",
    "load_mcp_tools",
    "purge_agent",
    "resolve_path",
    "save_skill",
    "tenant_skill_sources",
]
__version__ = "0.1.0"
