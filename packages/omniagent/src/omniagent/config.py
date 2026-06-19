"""运行配置:基于 ``pydantic-settings`` 从环境变量 / ``.env`` 读取。

**连接走 OpenAI 标准的 ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``**;**行为/模型走
``AGENT_`` 前缀**(OpenAI 没有对应项)。:func:`get_settings` 直接返回
:class:`Settings`,由 pydantic-settings 负责类型转换、``.env`` 加载与优先级
(环境变量 > ``.env`` > 默认值)。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: 内置默认端点(OpenAI 兼容 ``/v1``);未设 ``OPENAI_BASE_URL`` 时使用。
GATEWAY_BASE_URL = "https://aigateway-sandbox.mspbots.ai/v1"

#: PII(个人身份信息)处理策略。``"off"`` 表示不启用 PII 中间件。
PIIStrategy = Literal["off", "block", "redact", "mask", "hash"]


class Settings(BaseSettings):
    """deep agent 运行时配置。

    连接(OpenAI 标准变量):``OPENAI_BASE_URL`` · ``OPENAI_API_KEY``。
    行为:每个字段对应 ``AGENT_<FIELD_UPPER>`` 环境变量(如 ``AGENT_MODEL`` /
    ``AGENT_ENABLE_SHELL`` / ``AGENT_MODEL_CALL_LIMIT``)。
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),  # 允许 model / model_* 字段名
    )

    # —— 连接(OpenAI 标准变量,不带 AGENT_ 前缀) ——
    base_url: str = Field(default=GATEWAY_BASE_URL, validation_alias="OPENAI_BASE_URL")
    api_key: str = Field(default="anything", validation_alias="OPENAI_API_KEY")

    # —— 模型行为 ——
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.0
    fallback_model: str | None = None

    # —— 工作区 / skills ——
    workspace: str = ".agent"
    # skill 根:<skills_root>/public(全局)+ <skills_root>/<tenant>(租户共享)
    skills_root: str = ".agent/skills"

    # —— 能力开关 ——
    enable_shell: bool = True
    enable_file_search: bool = False
    enable_hitl: bool = False

    # —— 安全 ——
    pii_strategy: PIIStrategy = "off"

    # —— 运行约束 / 健壮性 ——
    model_call_limit: int | None = None
    tool_call_limit: int | None = None
    model_max_retries: int = 2
    tool_max_retries: int = 2

    # —— 上下文管理 ——
    context_edit_trigger_tokens: int = 100_000


def get_settings() -> Settings:
    """从环境变量 / ``.env`` 构建 :class:`Settings`(每次读取最新环境)。"""
    return Settings()


def export_openai_env(settings: Settings | None = None) -> None:
    """把生效的连接配置回填到 ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``(仅在未设置时)。

    连接本就读自 ``OPENAI_*``。但当用户依赖内置默认网关、未显式设 ``OPENAI_BASE_URL``
    时,需把默认值写回环境,好让 langchain 的其他 OpenAI 组件——尤其是 **embeddings**
    (如 Aegra 语义 store)——也走同一端点。已显式设置的 ``OPENAI_*`` 优先,不覆盖。
    """
    settings = settings or get_settings()
    os.environ.setdefault("OPENAI_API_KEY", settings.api_key)
    os.environ.setdefault("OPENAI_BASE_URL", settings.base_url)


def resolve_path(workspace: str | Path) -> Path:
    """把工作区配置解析为绝对路径(展开 ``~``,相对当前工作目录)。"""
    return Path(workspace).expanduser().resolve()


def safe_segment(name: str) -> str:
    """校验单段名称(租户 / agent / skill 名);拒绝空、``.``/``..`` 与路径分隔符。

    把不可信输入(``tenant`` / ``agent_id`` / skill 名)拼进文件路径前必须经此校验,
    防止目录穿越。
    """
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        msg = f"invalid name segment: {name!r}"
        raise ValueError(msg)
    return name
