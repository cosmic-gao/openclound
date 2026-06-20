"""工作区与 skill 路径解析。

工作目录按 ``(租户,用户,agent)`` 隔离,skill 按 ``(租户,agent)`` 隔离。
目录按需创建;删 agent 时 :func:`purge_agent` 清磁盘。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from omniagent.config import resolve_path, safe_segment


def init_workspace(workspace: str | Path) -> Path:
    """确保工作区目录存在(仅 mkdir),返回解析后的绝对路径。"""
    root = resolve_path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    return root


def skill_sources(skills_root: str | Path, tenant: str, agent: str) -> list[str]:
    """返回 skill 源 ``[<tenant>/<agent>]``(绝对 POSIX);每个 agent 独立维护一套。

    无全局公有层;目录缺失时自动创建(空目录加载为 0 个 skill)。
    """
    agent_dir = resolve_path(skills_root) / safe_segment(tenant) / safe_segment(agent)
    agent_dir.mkdir(parents=True, exist_ok=True)
    return [agent_dir.as_posix()]


def purge_agent(
    skills_root: str | Path, workspace: str | Path, tenant: str, agent: str
) -> dict[str, bool]:
    """删 agent 流程:清该 agent 的 per-agent skill 目录 + 所有用户的工作目录。

    Aegra ``DELETE /assistants/{id}`` 删 assistant 记录(权威);本函数清磁盘——
    skill ``<skills_root>/<tenant>/<agent>``,以及 workspace
    ``<workspace>/work/<tenant>/*/<agent>``(跨该 agent 的所有用户)。返回各部分是否删除。
    """
    tenant_s, agent_s = safe_segment(tenant), safe_segment(agent)
    removed: dict[str, bool] = {"skills": False, "work": False}

    skill_d = resolve_path(skills_root) / tenant_s / agent_s
    if skill_d.is_dir():
        shutil.rmtree(skill_d)
        removed["skills"] = True

    work_root = resolve_path(workspace) / "work" / tenant_s
    if work_root.is_dir():
        for user_dir in work_root.iterdir():
            agent_d = user_dir / agent_s
            if agent_d.is_dir():
                shutil.rmtree(agent_d)
                removed["work"] = True

    return removed
