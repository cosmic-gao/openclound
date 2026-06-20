"""把 :class:`~omniagent.config.AgentConfig` 合并为最终开关 :class:`ResolvedConfig`。

:func:`resolve` 三级合并(显式 > mode > Settings),并推导工具裁剪与 HITL 配置。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from omniagent.config import TOOL_ALIASES, AgentConfig, Mode, Settings

#: 每个 mode 的默认开关(被 AgentConfig 显式字段覆盖)。
MODE_DEFAULTS: dict[Mode, dict[str, bool]] = {
    "react": {"review_enabled": False},
    "pipeline": {"review_enabled": True},
}

REACT_PROMPT = (
    "You are a capable deep agent operating in a ReAct loop: think, call tools, "
    "observe results, and repeat. Use the todo tool to plan multi-step work, keep "
    "working notes in the file system, consult your skills for domain workflows, and "
    "delegate isolated subtasks to subagents. Be thorough and verify before finishing."
)

PIPELINE_PROMPT = (
    "You are a deep agent that follows a disciplined four-phase workflow:\n"
    "1. RETRIEVE — gather evidence first: search files (grep/glob), read sources, "
    "query MCP tools, and consult your skills before acting. Do not guess.\n"
    "2. PLAN — break the task into a todo list (write_todos) before executing.\n"
    "3. EXECUTE — carry out the plan step by step, keeping working notes in the file "
    "system and delegating isolated subtasks to subagents.\n"
    "4. REVIEW — before finishing, verify your work against the acceptance criteria "
    "and revise until it genuinely meets them.\n"
    "Be rigorous: evidence before claims, plan before action, verify before done."
)

MODE_PROMPTS: dict[Mode, str] = {"react": REACT_PROMPT, "pipeline": PIPELINE_PROMPT}


@dataclass
class ResolvedConfig:
    """合并后的最终开关,供 :func:`omniagent.builder.build_agent` 消费。"""

    mode: Mode
    model: str
    prompt: str
    temperature: float
    steps: int | None
    excluded_tools: list[str] = field(default_factory=list)
    interrupt_on: dict[str, bool] = field(default_factory=dict)
    review_enabled: bool = False
    rubric: str | None = None
    review_max_iterations: int = 3
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)


def _resolve_tools(cfg: AgentConfig) -> tuple[list[str], dict[str, bool]]:
    """``tools``/``permission`` → ``(excluded_tools, interrupt_on)``;未知键忽略。"""
    excluded: list[str] = []
    interrupt: dict[str, bool] = {}
    for cname, dname in TOOL_ALIASES.items():
        if cfg.tools.get(cname) is False or cfg.permission.get(cname) == "deny":
            excluded.append(dname)
        elif cfg.permission.get(cname) == "ask":
            interrupt[dname] = True
    return excluded, interrupt


def resolve(cfg: AgentConfig, settings: Settings) -> ResolvedConfig:
    """合并 :class:`AgentConfig` + :class:`Settings` 为 :class:`ResolvedConfig`。"""
    prompt = MODE_PROMPTS[cfg.mode]
    if cfg.prompt:
        prompt = f"{prompt}\n\n{cfg.prompt}"
    excluded, interrupt = _resolve_tools(cfg)
    review_enabled = (
        cfg.review.enabled
        if cfg.review.enabled is not None
        else MODE_DEFAULTS[cfg.mode]["review_enabled"]
    )
    return ResolvedConfig(
        mode=cfg.mode,
        model=cfg.model or settings.model,
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
    )


def fingerprint(resolved: ResolvedConfig) -> str:
    """图缓存键:影响图结构的字段序列化为稳定字符串。"""
    return json.dumps(
        {
            "mode": resolved.mode,
            "model": resolved.model,
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
        },
        sort_keys=True,
        ensure_ascii=False,
    )
