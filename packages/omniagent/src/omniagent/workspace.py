"""运行时工作区:agent 文件系统根 + skills / memories 资源。

首次使用时,从包内模板(``_data/``)把 ``skills/`` 与 ``memories/`` 复制到工作区,
避免直接读写已安装的包目录(只读 / 渲染环境)。后续运行若目标已存在则不覆盖,
以保留用户在工作区内的修改。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from omniagent.config import resolve_path, safe_segment

#: 包内随附的模板目录(示例 skills 与 memories)。
_DATA_DIR = Path(__file__).parent / "_data"

#: 工作区内会被初始化的子目录(对应 ``_data/`` 下的模板)。
_TEMPLATE_SUBDIRS = ("skills", "memories")


def init_workspace(workspace: str | Path, *, seed: bool = True) -> Path:
    """确保工作区目录存在;``seed=True`` 时从包内模板初始化 skills / memories。

    Args:
        workspace: 工作区目录(可为相对 / ``~`` 路径)。
        seed: 是否在子目录缺失时从 ``_data/`` 模板复制(单机/本地嵌入用 True;
            多租户 per-user 工作目录用 False,skill 改由 ``skill_sources`` 提供)。

    Returns:
        解析后的工作区绝对路径。
    """
    root = resolve_path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    if seed:
        for name in _TEMPLATE_SUBDIRS:
            src = _DATA_DIR / name
            dst = root / name
            if src.is_dir() and not dst.exists():
                shutil.copytree(src, dst)
    return root


def seed_public_skills(skills_root: str | Path) -> Path:
    """确保公有 skill 目录 ``<skills_root>/public`` 存在;为空时从 ``_data`` 初始化。

    返回公有 skill 目录的绝对路径。
    """
    public = resolve_path(skills_root) / "public"
    if not public.exists():
        src = _DATA_DIR / "skills"
        if src.is_dir():
            shutil.copytree(src, public)
        else:  # pragma: no cover - 模板缺失时仍建空目录
            public.mkdir(parents=True, exist_ok=True)
    return public


def skill_sources(skills_root: str | Path, tenant: str) -> list[str]:
    """返回 skill 源 ``[公有, 租户]``(绝对 POSIX 路径,同名时租户覆盖公有)。

    同租户的所有用户 / agent 共享租户 skill;目录缺失时自动创建。
    """
    root = resolve_path(skills_root)
    public = seed_public_skills(root)
    tenant_dir = root / safe_segment(tenant)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    return [public.as_posix(), tenant_dir.as_posix()]


def purge_agent(workspace: str | Path, tenant: str, user: str, agent: str) -> bool:
    """清除某用户某 agent 的工作目录 work/<tenant>/<user>/<agent>;不存在则返回 False。

    用于删 assistant 流程:Aegra ``DELETE /assistants/{id}`` 删记录(权威,按用户私有),
    本函数清该 agent 的磁盘工作目录(Aegra 不会清)。**租户共享 skill 不在此删** —— 它
    属租户、可被其他用户 / agent 复用,删租户 skill 走 skill 管理接口。
    """
    target = (
        resolve_path(workspace)
        / "work"
        / safe_segment(tenant)
        / safe_segment(user)
        / safe_segment(agent)
    )
    if target.is_dir():
        shutil.rmtree(target)
        return True
    return False


def has_skills(root: Path) -> bool:
    """工作区内是否存在至少一个含 ``SKILL.md`` 的技能目录。"""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return False
    return any(skills_dir.glob("*/SKILL.md"))


def memory_files(root: Path) -> list[str]:
    """返回工作区内可注入系统提示的记忆文件(相对工作区根的 POSIX 路径)。"""
    agents_md = root / "memories" / "AGENTS.md"
    if agents_md.is_file():
        return ["memories/AGENTS.md"]
    return []
