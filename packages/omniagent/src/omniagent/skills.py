"""skill 管理:对磁盘上 ``<skills_root>/<tenant>/<agent>/`` 的私有 skill 增删查。

skill 是一个目录(``SKILL.md`` + 可选多文件/脚本)。写入即生效:下一个新会话的
``SkillsMiddleware.before_agent`` 会从磁盘重扫加载(热更新),无需重启。

这些是纯函数(只碰文件系统),便于测试与复用;对外的 HTTP 入口见
:mod:`omniagent.http`。
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from omniagent.config import resolve_path, safe_segment


def _safe_relpath(path: str) -> Path:
    """校验 skill 内的相对文件路径(如 ``scripts/run.py``),拒绝绝对路径与 ``..``。"""
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        msg = f"invalid file path: {path!r}"
        raise ValueError(msg)
    return p


def skill_dir(skills_root: str | Path, tenant: str, agent: str, name: str) -> Path:
    """某私有 skill 的目录:``<skills_root>/<tenant>/<agent>/<name>``。"""
    root = resolve_path(skills_root)
    return root / safe_segment(tenant) / safe_segment(agent) / safe_segment(name)


def save_skill(
    skills_root: str | Path,
    tenant: str,
    agent: str,
    name: str,
    files: Mapping[str, str],
) -> Path:
    """写入 / 覆盖一个私有 skill;``files`` 为 ``{相对路径: 文本内容}``。

    至少需包含 ``SKILL.md``。返回该 skill 目录路径。写入后下个新会话即加载。
    """
    if "SKILL.md" not in files:
        msg = "files must include 'SKILL.md'"
        raise ValueError(msg)
    target = skill_dir(skills_root, tenant, agent, name)
    target.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        dest = target / _safe_relpath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return target


def delete_skill(skills_root: str | Path, tenant: str, agent: str, name: str) -> bool:
    """删除一个私有 skill 目录;不存在则返回 ``False``。"""
    target = skill_dir(skills_root, tenant, agent, name)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def list_skills(
    skills_root: str | Path, tenant: str, agent: str
) -> dict[str, list[str]]:
    """列出公有与该 ``(tenant, agent)`` 私有的 skill 名称。

    Returns:
        ``{"public": [...], "private": [...]}``,按名称排序。
    """
    root = resolve_path(skills_root)

    def _names(base: Path) -> list[str]:
        if not base.is_dir():
            return []
        return sorted(p.parent.name for p in base.glob("*/SKILL.md"))

    return {
        "public": _names(root / "public"),
        "private": _names(root / safe_segment(tenant) / safe_segment(agent)),
    }
