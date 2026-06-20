"""per-agent skill 增删查:assistant 的 backend root 下 ``skills/`` 目录。

一个 skill = 一个目录(``SKILL.md`` + 可选多文件 / 脚本),canonical 存于 agent root 内,
agent 经虚拟路径 ``/skills`` 读取。写盘即生效:下个新会话由 ``SkillsMiddleware`` 重扫。
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from omniagent.config import resolve_path, safe_segment


def _safe_relpath(path: str) -> Path:
    """校验 skill 内相对文件路径,拒绝绝对路径与 ``..``。"""
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        msg = f"invalid file path: {path!r}"
        raise ValueError(msg)
    return p


def skill_dir(agent_root: str | Path, name: str) -> Path:
    """``<agent_root>/skills/<name>``。"""
    return resolve_path(agent_root) / "skills" / safe_segment(name)


def save_skill(agent_root: str | Path, name: str, files: Mapping[str, str]) -> Path:
    """写入 / 覆盖一个 skill;``files`` 为 ``{相对路径: 文本}``,须含 ``SKILL.md``。"""
    if "SKILL.md" not in files:
        msg = "files must include 'SKILL.md'"
        raise ValueError(msg)
    target = skill_dir(agent_root, name)
    target.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        dest = target / _safe_relpath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return target


def delete_skill(agent_root: str | Path, name: str) -> bool:
    """删除一个 skill 目录;不存在返回 ``False``。"""
    target = skill_dir(agent_root, name)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def list_skills(agent_root: str | Path) -> list[str]:
    """列出该 agent 的 skill 名称(按名排序)。"""
    base = resolve_path(agent_root) / "skills"
    if not base.is_dir():
        return []
    return sorted(p.parent.name for p in base.glob("*/SKILL.md"))
