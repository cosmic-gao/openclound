"""openclound ``omniagent``:config 驱动、双形态、跨会话记忆的生产级 agent 基础包。

封装 LangChain ``deepagents``,作为 **Aegra 项目**部署(图入口见 ``graph.py``)。
形态与开关由每个 assistant 的 ``config.configurable`` 决定(见 :class:`AgentConfig`)。
模型统一经 ``langchain_openai`` 接入任意 OpenAI 兼容端点 / 第三方网关,
连接 per-assistant 必填、无默认。
"""

from omniagent.builder import AGENT_NAME, ToolFilter, build_agent
from omniagent.config import (
    AgentConfig,
    Permission,
    PIIStrategy,
    ReviewConfig,
    Settings,
    get_settings,
    resolve_path,
    safe_segment,
)
from omniagent.mcp import load_mcp_tools
from omniagent.memory import MEMORY_FILE, build_backend, memory_sources
from omniagent.middleware import build_middleware
from omniagent.model import build_model
from omniagent.resolve import (
    DEFAULT_PROMPT,
    PIPELINE_PROMPT,
    ResolvedConfig,
    fingerprint,
    resolve,
)
from omniagent.review import build_review_middleware
from omniagent.workspace import (
    agent_root,
    delete_skill,
    init_workspace,
    list_skills,
    purge_agent,
    save_skill,
    skill_signature,
    skill_sources,
)

__all__ = [
    "AGENT_NAME",
    "DEFAULT_PROMPT",
    "MEMORY_FILE",
    "PIPELINE_PROMPT",
    "AgentConfig",
    "PIIStrategy",
    "Permission",
    "ResolvedConfig",
    "ReviewConfig",
    "Settings",
    "ToolFilter",
    "agent_root",
    "build_agent",
    "build_backend",
    "build_middleware",
    "build_model",
    "build_review_middleware",
    "delete_skill",
    "fingerprint",
    "get_settings",
    "init_workspace",
    "list_skills",
    "load_mcp_tools",
    "memory_sources",
    "purge_agent",
    "resolve",
    "resolve_path",
    "safe_segment",
    "save_skill",
    "skill_signature",
    "skill_sources",
]
__version__ = "0.1.0"
