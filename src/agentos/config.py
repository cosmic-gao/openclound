"""配置:进程级 ``Settings`` + 请求级 ``AgentConfig``,``resolve`` 合并为 ``ResolvedConfig``。

连接(model/base_url/api_key)per-assistant 显式分配,缺失回退 env,无硬编码默认。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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

#: 基础系统指令(自由 ReAct;叠加在 config.prompt 之前)。
DEFAULT_PROMPT = (
    "You are a capable deep agent operating in a ReAct loop: think, call tools, "
    "observe results, and repeat. Use the todo tool to plan multi-step work, keep "
    "working notes in the file system, consult your skills for domain workflows, and "
    "delegate isolated subtasks to subagents. Be thorough and verify before finishing."
)

#: 可选纪律提示:放进 config.prompt 即得「检索→规划→执行→审核」管线行为。
PIPELINE_PROMPT = (
    "Follow a disciplined four-phase workflow:\n"
    "1. RETRIEVE — gather evidence first: search files (grep/glob), read sources, "
    "query MCP tools, and consult your skills before acting. Do not guess.\n"
    "2. PLAN — break the task into a todo list (write_todos) before executing.\n"
    "3. EXECUTE — carry out the plan step by step, keeping working notes in the file "
    "system and delegating isolated subtasks to subagents.\n"
    "4. REVIEW — before finishing, verify your work against the acceptance criteria "
    "and revise until it genuinely meets them.\n"
    "Be rigorous: evidence before claims, plan before action, verify before done."
)


class Settings(BaseSettings):
    """进程级配置;连接默认(env)在 assistant config 缺失对应项时回退到此。"""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    workspace: str = ".agent"

    model: str | None = None  # AGENT_MODEL
    base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    temperature: float | None = None
    fallback_model: str | None = None

    model_max_retries: int = 2
    tool_max_retries: int = 2
    tool_call_limit: int | None = None
    pii_strategy: PIIStrategy = "off"
    enable_file_search: bool = False


class ReviewConfig(BaseModel):
    """审核开关;装配见 ``build_review_middleware``。"""

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


@dataclass(frozen=True)
class ResolvedConfig:
    """:func:`resolve` 产出的只读最终开关,供 ``build_agent`` 消费。"""

    model: str | None
    base_url: str | None
    api_key: str | None
    prompt: str
    temperature: float | None
    steps: int | None
    excluded_tools: list[str] = field(default_factory=list)
    interrupt_on: dict[str, bool] = field(default_factory=dict)
    review_enabled: bool = False
    rubric: str | None = None
    review_max_iterations: int = 3
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    model_params: dict[str, Any] = field(default_factory=dict)
    memory: bool = False
    fallback_model: str | None = None
    pii_strategy: PIIStrategy = "off"
    enable_file_search: bool = False


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


def _resolve_tools(cfg: AgentConfig) -> tuple[list[str], dict[str, bool]]:
    """``tools``/``permission`` → ``(excluded_tools, interrupt_on)``。"""
    excluded: list[str] = []
    interrupt: dict[str, bool] = {}
    for cname, dname in TOOL_ALIASES.items():
        if cfg.tools.get(cname) is False or cfg.permission.get(cname) == "deny":
            excluded.append(dname)
        elif cfg.permission.get(cname) == "ask":
            interrupt[dname] = True
    return excluded, interrupt


def resolve(cfg: AgentConfig, settings: Settings) -> ResolvedConfig:
    """合并 ``AgentConfig`` + ``Settings``(显式 config 优先,缺失回退 env)。"""
    prompt = f"{DEFAULT_PROMPT}\n\n{cfg.prompt}" if cfg.prompt else DEFAULT_PROMPT
    excluded, interrupt = _resolve_tools(cfg)
    review_enabled = (
        cfg.review.enabled
        if cfg.review.enabled is not None
        else bool(cfg.review.rubric)
    )
    return ResolvedConfig(
        model=cfg.model or settings.model,
        base_url=cfg.base_url or settings.base_url,
        api_key=cfg.api_key or settings.api_key,
        prompt=prompt,
        temperature=(
            cfg.temperature if cfg.temperature is not None else settings.temperature
        ),
        steps=cfg.steps,
        excluded_tools=excluded,
        interrupt_on=interrupt,
        review_enabled=review_enabled,
        rubric=cfg.review.rubric,
        review_max_iterations=cfg.review.max_iterations,
        mcp_servers=dict(cfg.mcp),
        model_params=dict(cfg.model_params),
        memory=cfg.memory,
        fallback_model=cfg.fallback_model or settings.fallback_model,
        pii_strategy=cfg.pii_strategy or settings.pii_strategy,
        enable_file_search=(
            cfg.enable_file_search
            if cfg.enable_file_search is not None
            else settings.enable_file_search
        ),
    )


def fingerprint(resolved: ResolvedConfig, skill_sig: str = "") -> str:
    """图缓存键:序列化影响图结构的配置(剔除 api_key)+ skill 签名。"""
    data = {k: v for k, v in asdict(resolved).items() if k != "api_key"}
    data["skills"] = skill_sig
    return json.dumps(data, sort_keys=True, ensure_ascii=False)
