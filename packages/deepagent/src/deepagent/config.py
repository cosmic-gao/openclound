"""运行配置:litellm 网关 + 运行时参数 + 环境/密钥加载。

所有面向用户的配置项集中在 :class:`Settings`,通过 :func:`get_settings`
从环境变量(``DEEPAGENT_*``)读取并填充默认值。``get_settings`` 每次返回
一个新的 :class:`Settings` 实例(纯读环境,无副作用),便于测试时覆盖环境。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

#: openclound 内部 litellm 网关(OpenAI 兼容 ``/v1`` 接口)。
#: 网关负责把 OpenAI 风格的请求路由到实际后端模型(如 Claude),
#: 因此本包统一用 :class:`langchain_openai.ChatOpenAI` 对接。
GATEWAY_BASE_URL = "https://aigateway-sandbox.mspbots.ai/v1"

#: PII(个人身份信息)处理策略。``"off"`` 表示不启用 PII 中间件。
PIIStrategy = Literal["off", "block", "redact", "mask", "hash"]


def _load_dotenv() -> None:
    """加载当前工作目录下的 ``.env``(若存在)。

    已在环境中显式设置的变量优先(``override=False``),因此 shell / CLI 传入的值
    会盖过 ``.env``。只读取 ``cwd/.env``(不向上递归),行为可预期。
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv 未安装时静默跳过
        return
    load_dotenv(Path.cwd() / ".env", override=False)


def _flag(name: str, default: bool) -> bool:  # noqa: FBT001
    """读取布尔型环境变量(``1`` / ``true`` / ``yes`` / ``on`` 视为真)。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int | None) -> int | None:
    """读取整型环境变量;为空或非法时回退默认值。"""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    """读取浮点型环境变量;为空或非法时回退默认值。"""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


@dataclass(slots=True)
class Settings:
    """deep agent 运行时配置。

    字段对应环境变量见 :func:`get_settings`。
    """

    # —— 模型 / 网关 ——
    base_url: str = GATEWAY_BASE_URL
    api_key: str = "anything"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.0
    fallback_model: str | None = None

    # —— 工作区 ——
    workspace: str = ".deepagent"

    # —— 能力开关 ——
    enable_shell: bool = True
    enable_file_search: bool = False
    enable_hitl: bool = False

    # —— 安全 ——
    pii_strategy: PIIStrategy = "off"

    # —— 运行约束 / 健壮性 ——
    model_call_run_limit: int | None = None
    tool_call_run_limit: int | None = None
    model_max_retries: int = 2
    tool_max_retries: int = 2

    # —— 上下文管理 ——
    context_edit_trigger_tokens: int = 100_000
    summarize_trigger_tokens: int | None = None
    summarize_keep_messages: int = 20


def get_settings() -> Settings:
    """从环境变量构建 :class:`Settings`(含合理默认值)。

    识别的环境变量:

    模型 / 网关
        ``DEEPAGENT_BASE_URL`` · ``DEEPAGENT_API_KEY``(回退 ``OPENAI_API_KEY``)
        · ``DEEPAGENT_MODEL`` · ``DEEPAGENT_TEMPERATURE`` · ``DEEPAGENT_FALLBACK_MODEL``

    工作区
        ``DEEPAGENT_WORKSPACE``

    能力开关
        ``DEEPAGENT_ENABLE_SHELL`` · ``DEEPAGENT_ENABLE_FILE_SEARCH``
        · ``DEEPAGENT_ENABLE_HITL``

    安全
        ``DEEPAGENT_PII_STRATEGY``

    运行约束 / 上下文
        ``DEEPAGENT_MODEL_CALL_LIMIT`` · ``DEEPAGENT_TOOL_CALL_LIMIT``
        · ``DEEPAGENT_MODEL_MAX_RETRIES`` · ``DEEPAGENT_TOOL_MAX_RETRIES``
        · ``DEEPAGENT_CONTEXT_EDIT_TRIGGER_TOKENS``
        · ``DEEPAGENT_SUMMARIZE_TRIGGER_TOKENS`` · ``DEEPAGENT_SUMMARIZE_KEEP_MESSAGES``

    启动时会先加载工作目录下的 ``.env``(见 :func:`_load_dotenv`)。
    """
    _load_dotenv()

    pii = os.getenv("DEEPAGENT_PII_STRATEGY", "off").strip().lower()
    pii_strategy: PIIStrategy = (
        pii if pii in {"off", "block", "redact", "mask", "hash"} else "off"  # type: ignore[assignment]
    )

    return Settings(
        base_url=os.getenv("DEEPAGENT_BASE_URL", GATEWAY_BASE_URL),
        api_key=(
            os.getenv("DEEPAGENT_API_KEY") or os.getenv("OPENAI_API_KEY") or "anything"
        ),
        model=os.getenv("DEEPAGENT_MODEL", "claude-sonnet-4-6"),
        temperature=_float("DEEPAGENT_TEMPERATURE", 0.0),
        fallback_model=os.getenv("DEEPAGENT_FALLBACK_MODEL") or None,
        workspace=os.getenv("DEEPAGENT_WORKSPACE", ".deepagent"),
        enable_shell=_flag("DEEPAGENT_ENABLE_SHELL", default=True),
        enable_file_search=_flag("DEEPAGENT_ENABLE_FILE_SEARCH", default=False),
        enable_hitl=_flag("DEEPAGENT_ENABLE_HITL", default=False),
        pii_strategy=pii_strategy,
        model_call_run_limit=_int("DEEPAGENT_MODEL_CALL_LIMIT", None),
        tool_call_run_limit=_int("DEEPAGENT_TOOL_CALL_LIMIT", None),
        model_max_retries=_int("DEEPAGENT_MODEL_MAX_RETRIES", 2) or 0,
        tool_max_retries=_int("DEEPAGENT_TOOL_MAX_RETRIES", 2) or 0,
        context_edit_trigger_tokens=_int(
            "DEEPAGENT_CONTEXT_EDIT_TRIGGER_TOKENS", 100_000
        )
        or 0,
        summarize_trigger_tokens=_int("DEEPAGENT_SUMMARIZE_TRIGGER_TOKENS", None),
        summarize_keep_messages=_int("DEEPAGENT_SUMMARIZE_KEEP_MESSAGES", 20) or 20,
    )


def resolve_workspace(workspace: str | Path) -> Path:
    """把工作区配置解析为绝对路径(展开 ``~``,相对当前工作目录)。"""
    return Path(workspace).expanduser().resolve()
