"""工作区路径:assistant 的 backend root = ``<base>/tenant-<id>/assistant-<id>``。

skill 在 root 下 ``skills/``,agent 经虚拟路径 ``/skills`` 读取。删 agent 时
:func:`purge_agent` 移除整个 root(skill + 运行期文件)。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from omniagent.config import resolve_path, safe_segment


def agent_root(base: str | Path, tenant: str, agent: str) -> Path:
    """某 assistant 的 backend root:``<base>/tenant-<tenant>/assistant-<agent>``。

    ``tenant-`` / ``assistant-`` 前缀自描述,跨平台文件名合法。
    """
    return (
        resolve_path(base)
        / f"tenant-{safe_segment(tenant)}"
        / f"assistant-{safe_segment(agent)}"
    )


def init_workspace(path: str | Path) -> Path:
    """确保目录存在(mkdir),返回绝对路径。"""
    root = resolve_path(path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def skill_sources(root: str | Path) -> list[str]:
    """该 agent 有 skill 时返回虚拟源 ``["/skills"]``,否则 ``[]``。"""
    skills = resolve_path(root) / "skills"
    if skills.is_dir() and any(skills.glob("*/SKILL.md")):
        return ["/skills"]
    return []


def purge_agent(root: str | Path) -> bool:
    """删 agent:移除其整个 backend root(skill + 运行期文件);不存在返回 ``False``。"""
    target = resolve_path(root)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True
