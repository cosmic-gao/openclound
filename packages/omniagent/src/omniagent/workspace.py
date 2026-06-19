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
            多租户 per-agent 工作目录用 False(skill 改由 ``skill_sources`` 提供)。

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


def tenant_skill_sources(skills_root: str | Path, tenant: str, agent: str) -> list[str]:
    """返回某 ``(tenant, agent)`` 的 skill 源:``[公有, 私有]``(绝对 POSIX 路径)。

    公有在前、私有在后 —— 同名时私有覆盖公有(``SkillsMiddleware`` "后者优先")。
    私有目录缺失时自动创建(空目录会被安全地加载为 0 个 skill)。
    """
    root = resolve_path(skills_root)
    public = seed_public_skills(root)
    private = root / safe_segment(tenant) / safe_segment(agent)
    private.mkdir(parents=True, exist_ok=True)
    return [public.as_posix(), private.as_posix()]


def purge_agent(
    skills_root: str | Path, workspace: str | Path, tenant: str, agent: str
) -> dict[str, bool]:
    """清除某 agent 在 agent 侧的本地文件:私有 skill 目录 + 工作目录。

    用于删 agent 流程:Aegra ``DELETE /assistants/{id}`` 删 assistant 记录(权威),本
    函数清磁盘文件(Aegra 不会清)。命名为 ``purge`` 以区别于"删除 agent 记录"。
    返回各目录是否被删除。
    """
    tenant_s, agent_s = safe_segment(tenant), safe_segment(agent)
    targets = {
        "skills": resolve_path(skills_root) / tenant_s / agent_s,
        "work": resolve_path(workspace) / "work" / tenant_s / agent_s,
    }
    removed: dict[str, bool] = {}
    for label, path in targets.items():
        if path.is_dir():
            shutil.rmtree(path)
            removed[label] = True
        else:
            removed[label] = False
    return removed


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
