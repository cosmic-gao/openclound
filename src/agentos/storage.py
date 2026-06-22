"""assistant 磁盘存储:root = ``<base>/<agent>``;含路径、skill 发现与文件级 CRUD。"""

from __future__ import annotations

import shutil
from pathlib import Path

from agentos.config import resolve_path, safe_segment


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


def _skill_file(root: str | Path, name: str, path: str) -> Path:
    """skill 内某文件的绝对路径(名段 + 相对路径双重校验)。"""
    return _skill_dir(root, name) / _safe_relpath(path)


def list_skills(root: str | Path) -> list[str]:
    """列出 skill 名称(按名排序)。"""
    base = resolve_path(root) / "skills"
    if not base.is_dir():
        return []
    return sorted(p.parent.name for p in base.glob("*/SKILL.md"))


def delete_skill(root: str | Path, name: str) -> bool:
    """删除整个 skill 目录;不存在返回 ``False``。"""
    target = _skill_dir(root, name)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True


def list_skill_files(root: str | Path, name: str) -> list[str]:
    """列出某 skill 下全部文件的相对路径(posix,已排序);skill 不存在返回 ``[]``。"""
    target = _skill_dir(root, name)
    if not target.is_dir():
        return []
    return sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()
    )


def read_skill_file(root: str | Path, name: str, path: str) -> str:
    """读取 skill 内某文件文本;不存在抛 ``FileNotFoundError``。"""
    target = _skill_file(root, name, path)
    if not target.is_file():
        msg = f"skill file not found: {path!r}"
        raise FileNotFoundError(msg)
    return target.read_text(encoding="utf-8")


def write_skill_file(root: str | Path, name: str, path: str, content: str) -> Path:
    """写入/覆盖 skill 内某文件(任意相对路径,自动建父目录);兼作新增与保存。"""
    target = _skill_file(root, name, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def rename_skill_file(root: str | Path, name: str, src: str, dst: str) -> Path:
    """重命名/移动 skill 内文件;源不存在抛 ``FileNotFoundError``。"""
    src_path = _skill_file(root, name, src)
    dst_path = _skill_file(root, name, dst)
    if not src_path.is_file():
        msg = f"skill file not found: {src!r}"
        raise FileNotFoundError(msg)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    src_path.rename(dst_path)
    return dst_path


def delete_skill_file(root: str | Path, name: str, path: str) -> bool:
    """删除 skill 内某文件;不存在返回 ``False``。"""
    target = _skill_file(root, name, path)
    if not target.is_file():
        return False
    target.unlink()
    return True


def purge_agent(root: str | Path) -> bool:
    """删该 assistant 的整个 backend root(skill + 运行期文件);不存在返回 ``False``。"""
    target = resolve_path(root)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True
