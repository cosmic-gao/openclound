"""把 ``AgentConfig`` + ``Settings`` 合并为 ``ResolvedConfig``(配置驱动,无 mode)。

审核仅在给了 ``review.rubric`` 且未显式关闭时激活;:func:`fingerprint` 产出图缓存键
(剔除 api_key、纳入 skill 签名)。管线纪律见 ``PIPELINE_PROMPT``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from omniagent.config import TOOL_ALIASES, AgentConfig, PIIStrategy, Settings

#: 基础系统指令(自由 ReAct;叠加在 config.prompt 之前)。
DEFAULT_PROMPT = (
    "You are a capable deep agent operating in a ReAct loop: think, call tools, "
    "observe results, and repeat. Use the todo tool to plan multi-step work, keep "
    "working notes in the file system, consult your skills for domain workflows, and "
    "delegate isolated subtasks to subagents. Be thorough and verify before finishing."
)

#: 可选纪律提示:放进 ``config.prompt`` 即得「检索→规划→执行→审核」管线行为。
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


@dataclass(frozen=True)
class ResolvedConfig:
    """合并后的最终开关(只读),供 :func:`omniagent.builder.build_agent` 消费。"""

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
    """合并 :class:`AgentConfig` + :class:`Settings`。"""
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
    """图缓存键:影响图结构的字段序列化为稳定字符串(``api_key`` 不入键)。"""
    return json.dumps(
        {
            "model": resolved.model,
            "base_url": resolved.base_url,
            "prompt": resolved.prompt,
            "temperature": resolved.temperature,
            "steps": resolved.steps,
            "excluded": sorted(resolved.excluded_tools),
            "interrupt": sorted(resolved.interrupt_on),
            "review": [
                resolved.review_enabled,
                resolved.rubric,
                resolved.review_max_iterations,
            ],
            "mcp": resolved.mcp_servers,
            "model_params": resolved.model_params,
            "memory": resolved.memory,
            "fallback_model": resolved.fallback_model,
            "pii_strategy": resolved.pii_strategy,
            "enable_file_search": resolved.enable_file_search,
            "skills": skill_sig,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
