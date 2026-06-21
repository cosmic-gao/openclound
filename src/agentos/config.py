"""配置:进程级 ``Settings``(运行参数,无连接)+ 请求级 ``AgentConfig``(per-assistant)。

连接(model/base_url/api_key)必须 per-assistant 显式分配,无默认;由
:func:`agentos.spec.resolve` 合并为最终开关。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

PIIStrategy = Literal["off", "block", "redact", "mask", "hash"]
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
    """进程级配置;含模型连接默认(env),assistant config 缺失对应项时回退到此。"""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    workspace: str = ".agent"

    # 模型连接默认(env);assistant config 未配对应项时回退到此,无硬编码默认。
    model: str | None = None  # AGENT_MODEL
    base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    temperature: float | None = None  # AGENT_TEMPERATURE
    fallback_model: str | None = None  # AGENT_FALLBACK_MODEL

    model_max_retries: int = 2
    tool_max_retries: int = 2
    tool_call_limit: int | None = None
    context_edit_trigger_tokens: int = 100_000
    pii_strategy: PIIStrategy = "off"
    enable_file_search: bool = False


class ReviewConfig(BaseModel):
    """审核开关(装配见 :func:`agentos.middleware.build_review_middleware`)。"""

    model_config = ConfigDict(extra="ignore")

    enabled: bool | None = None
    rubric: str | None = None
    max_iterations: int = 3


class AgentConfig(BaseModel):
    """per-assistant 配置(opencode / Claude 风格);连接必填,其余可选。"""

    model_config = ConfigDict(extra="ignore")

    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # ⚠ 入 config 即明文存库
    prompt: str | None = None
    temperature: float | None = None
    model_params: dict[str, Any] = Field(default_factory=dict)
    steps: int | None = None
    tools: dict[str, bool] = Field(default_factory=dict)
    permission: dict[str, Permission] = Field(default_factory=dict)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    mcp: dict[str, dict[str, Any]] = Field(default_factory=dict)
    memory: bool = False
    fallback_model: str | None = None
    pii_strategy: PIIStrategy | None = None
    enable_file_search: bool | None = None

    @classmethod
    def parse(cls, configurable: dict[str, Any] | None) -> AgentConfig:
        """从 ``config.configurable`` 容错解析;失败回退默认。"""
        try:
            return cls.model_validate(configurable or {})
        except ValidationError:
            return cls()


def get_settings() -> Settings:
    return Settings()


def resolve_path(workspace: str | Path) -> Path:
    """解析为绝对路径(展开 ``~``)。"""
    return Path(workspace).expanduser().resolve()


def safe_segment(name: str) -> str:
    """校验单段路径名(agent / skill),拒绝空、``.``/``..`` 与分隔符。"""
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        msg = f"invalid name segment: {name!r}"
        raise ValueError(msg)
    return name
