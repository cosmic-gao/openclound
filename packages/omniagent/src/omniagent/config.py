"""配置:进程级 ``Settings`` + 请求级 ``AgentConfig``。

``Settings`` 来自环境 / ``.env``(部署级默认与连接);``AgentConfig`` 来自每个 assistant 的
``config.configurable``(opencode / Claude 风格的 per-agent 开关),由
:func:`omniagent.modes.resolve` 合并为最终开关。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

#: 内置默认端点(OpenAI 兼容 ``/v1``);未设 ``OPENAI_BASE_URL`` 时使用。
GATEWAY_BASE_URL = "https://aigateway-sandbox.mspbots.ai/v1"

#: PII 处理策略;``off`` 表示不启用。
PIIStrategy = Literal["off", "block", "redact", "mask", "hash"]

#: agent 形态:``react``=自由 ReAct;``pipeline``=检索→规划→执行→审核。
Mode = Literal["react", "pipeline"]

#: 工具权限:放行 / 人工确认(HITL)/ 拒绝(移除)。
Permission = Literal["allow", "ask", "deny"]

#: config 工具名 → deepagents 内置工具名。
TOOL_ALIASES: dict[str, str] = {
    "bash": "execute",
    "write": "write_file",
    "edit": "edit_file",
    "read": "read_file",
    "glob": "glob",
    "grep": "grep",
    "task": "task",
}


class Settings(BaseSettings):
    """进程级配置(部署默认 / fallback);连接走 ``OPENAI_*``,行为走 ``AGENT_*``。"""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    base_url: str = Field(default=GATEWAY_BASE_URL, validation_alias="OPENAI_BASE_URL")
    api_key: str = Field(default="anything", validation_alias="OPENAI_API_KEY")

    model: str = "claude-sonnet-4-6"
    temperature: float = 0.0
    fallback_model: str | None = None

    # 每个 assistant 的 backend root = <base>/tenant-<id>/assistant-<id>
    workspace: str = ".agent"

    model_max_retries: int = 2
    tool_max_retries: int = 2
    tool_call_limit: int | None = None
    context_edit_trigger_tokens: int = 100_000

    pii_strategy: PIIStrategy = "off"
    enable_file_search: bool = False


class ReviewConfig(BaseModel):
    """审核开关(pipeline 的"审核"步,见 :mod:`omniagent.review`)。"""

    model_config = ConfigDict(extra="ignore")

    enabled: bool | None = None  # None=继承 mode 默认
    rubric: str | None = None  # 为空则审核不激活
    max_iterations: int = 3


class AgentConfig(BaseModel):
    """per-assistant 配置(opencode / Claude 风格);全部可选,缺省继承 mode / Settings。"""

    model_config = ConfigDict(extra="ignore")

    mode: Mode = "react"
    model: str | None = None
    prompt: str | None = None  # 场景指令,叠加在 mode 提示之后
    temperature: float | None = None
    steps: int | None = None  # 最大模型迭代(opencode: steps)
    tools: dict[str, bool] = Field(default_factory=dict)  # false=移除该工具
    permission: dict[str, Permission] = Field(default_factory=dict)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    mcp: dict[str, dict[str, Any]] = Field(default_factory=dict)  # per-agent 检索源

    @classmethod
    def parse(cls, configurable: dict[str, Any] | None) -> AgentConfig:
        """从 ``config.configurable`` 容错解析;失败回退默认。"""
        try:
            return cls.model_validate(configurable or {})
        except ValidationError:
            return cls()


def get_settings() -> Settings:
    """读取最新环境 / ``.env`` 构建 :class:`Settings`。"""
    return Settings()


def export_openai_env(settings: Settings | None = None) -> None:
    """把网关回填到 ``OPENAI_*``(仅未设置时),让 embeddings 等也走同一端点。"""
    settings = settings or get_settings()
    os.environ.setdefault("OPENAI_API_KEY", settings.api_key)
    os.environ.setdefault("OPENAI_BASE_URL", settings.base_url)


def resolve_path(workspace: str | Path) -> Path:
    """解析为绝对路径(展开 ``~``,相对 cwd)。"""
    return Path(workspace).expanduser().resolve()


def safe_segment(name: str) -> str:
    """校验单段路径名(租户 / 用户 / agent / skill),拒绝空、``.``/``..`` 与分隔符。"""
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        msg = f"invalid name segment: {name!r}"
        raise ValueError(msg)
    return name
