"""openclound ``omniagent``:config 驱动、双形态、多租户的 agent 基础包。

封装 LangChain ``deepagents``,作为 **Aegra 项目**部署(图入口见 ``graph.py``)。
形态与开关由每个 assistant 的 ``config.configurable`` 决定(见 :class:`AgentConfig`)。
"""

from omniagent.builder import AGENT_NAME, build_agent
from omniagent.config import (
    GATEWAY_BASE_URL,
    AgentConfig,
    Mode,
    PIIStrategy,
    ReviewConfig,
    Settings,
    export_openai_env,
    get_settings,
    resolve_path,
    safe_segment,
)
from omniagent.mcp import load_mcp_tools
from omniagent.middleware import build_middleware
from omniagent.model import build_model
from omniagent.modes import ResolvedConfig, fingerprint, resolve
from omniagent.review import build_review_middleware
from omniagent.skills import delete_skill, list_skills, save_skill
from omniagent.workspace import agent_root, init_workspace, purge_agent, skill_sources

__all__ = [
    "AGENT_NAME",
    "GATEWAY_BASE_URL",
    "AgentConfig",
    "Mode",
    "PIIStrategy",
    "ResolvedConfig",
    "ReviewConfig",
    "Settings",
    "agent_root",
    "build_agent",
    "build_middleware",
    "build_model",
    "build_review_middleware",
    "delete_skill",
    "export_openai_env",
    "fingerprint",
    "get_settings",
    "init_workspace",
    "list_skills",
    "load_mcp_tools",
    "purge_agent",
    "resolve",
    "resolve_path",
    "safe_segment",
    "save_skill",
    "skill_sources",
]
__version__ = "0.1.0"
