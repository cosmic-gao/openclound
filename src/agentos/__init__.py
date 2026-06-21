"""openclound ``agentos``:config 驱动、双形态、跨会话记忆的生产级 agent 基础包。

封装 LangChain ``deepagents``,作为 **Aegra 项目**部署(图入口见 ``graph.py``)。
形态与开关由每个 assistant 的 ``config.configurable`` 决定(见 :class:`AgentConfig`)。
模型统一经 ``langchain_openai`` 接入任意兼容端点 / 网关;
连接 per-assistant 必填,缺失回退 env。
"""

from agentos.builder import AGENT_NAME, build_agent
from agentos.config import (
    AgentConfig,
    Permission,
    PIIStrategy,
    ReviewConfig,
    Settings,
    get_settings,
    resolve_path,
    safe_segment,
)
from agentos.mcp import load_mcp_tools
from agentos.memory import MEMORY_FILE, build_backend, memory_sources
from agentos.middleware import ToolFilter, build_middleware, build_review_middleware
from agentos.model import build_model
from agentos.spec import (
    DEFAULT_PROMPT,
    PIPELINE_PROMPT,
    ResolvedConfig,
    fingerprint,
    resolve,
)
from agentos.storage import (
    agent_root,
    delete_skill,
    delete_skill_file,
    init_workspace,
    list_skill_files,
    list_skills,
    purge_agent,
    read_skill_file,
    rename_skill_file,
    skill_signature,
    skill_sources,
    write_skill_file,
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
    "delete_skill_file",
    "fingerprint",
    "get_settings",
    "init_workspace",
    "list_skill_files",
    "list_skills",
    "load_mcp_tools",
    "memory_sources",
    "purge_agent",
    "read_skill_file",
    "rename_skill_file",
    "resolve",
    "resolve_path",
    "safe_segment",
    "skill_signature",
    "skill_sources",
    "write_skill_file",
]
__version__ = "0.1.0"
