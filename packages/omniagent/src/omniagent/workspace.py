"""assistant 的磁盘工作区:backend root = ``<base>/<agent>``,skill 在其下 ``skills/``。

路径与生命周期(agent_root / init / purge)、build 期 skill 发现(sources / signature)、
skill 内容 CRUD(save / list / delete)。skill 按 assistant 隔离。
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from omniagent.config import resolve_path, safe_segment


def agent_root(base: str | Path, agent: str) -> Path:
    """该 assistant 的 backend root:``<base>/<agent>``。"""
    return resolve_path(base) / safe_segment(agent)


def init_workspace(path: str | Path) -> Path:
    """确保目录存在,返回绝对路径。"""
    root = resolve_path(path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def skill_sources(root: str | Path) -> list[str]:
    """有 skill 时返回虚拟源 ``["/skills"]``,否则 ``[]``。"""
    skills = resolve_path(root) / "skills"
    if skills.is_dir() and any(skills.glob("*/SKILL.md")):
        return ["/skills"]
    return []


def skill_signature(root: str | Path) -> str:
    """skill 集合签名(``名:mtime``);用于图缓存键,skill 增删改触发重建。"""
    skills = resolve_path(root) / "skills"
    if not skills.is_dir():
        return ""
    parts: list[str] = []
    for marker in sorted(skills.glob("*/SKILL.md")):
        try:
            mtime = marker.stat().st_mtime_ns
        except OSError:
            mtime = 0
        parts.append(f"{marker.parent.name}:{mtime}")
    return ";".join(parts)


def _skill_dir(root: str | Path, name: str) -> Path:
    return resolve_path(root) / "skills" / safe_segment(name)


def _safe_relpath(path: str) -> Path:
    """校验 skill 内相对路径,拒绝绝对路径与 ``..``。"""
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        msg = f"invalid file path: {path!r}"
        raise ValueError(msg)
    return p


def save_skill(root: str | Path, name: str, files: Mapping[str, str]) -> Path:
    """写入 / 覆盖一个 skill;``files`` 为 ``{相对路径: 文本}``,须含 ``SKILL.md``。"""
    if "SKILL.md" not in files:
        msg = "files must include 'SKILL.md'"
        raise ValueError(msg)
    target = _skill_dir(root, name)
    target.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        dest = target / _safe_relpath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return target


def list_skills(root: str | Path) -> list[str]:
    """列出 skill 名称(按名排序)。"""
    base = resolve_path(root) / "skills"
    if not base.is_dir():
        return []
    return sorted(p.parent.name for p in base.glob("*/SKILL.md"))


def delete_skill(root: str | Path, name: str) -> bool:
    """删除一个 skill 目录;不存在返回 ``False``。"""
    target = _skill_dir(root, name)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def purge_agent(root: str | Path) -> bool:
    """删该 assistant 的整个 backend root(skill + 运行期文件);不存在返回 ``False``。"""
    target = resolve_path(root)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True
