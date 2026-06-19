"""运行时工作区:agent 文件系统根 + skills / memories 资源。

首次使用时,从包内模板(``_data/``)把 ``skills/`` 与 ``memories/`` 复制到工作区,
避免直接读写已安装的包目录(只读 / 渲染环境)。后续运行若目标已存在则不覆盖,
以保留用户在工作区内的修改。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from deepagent.config import resolve_path

#: 包内随附的模板目录(示例 skills 与 memories)。
_DATA_DIR = Path(__file__).parent / "_data"

#: 工作区内会被初始化的子目录(对应 ``_data/`` 下的模板)。
_TEMPLATE_SUBDIRS = ("skills", "memories")


def init_workspace(workspace: str | Path) -> Path:
    """确保工作区就绪;子目录缺失时从模板初始化。

    Args:
        workspace: 工作区目录(可为相对 / ``~`` 路径)。

    Returns:
        解析后的工作区绝对路径。
    """
    root = resolve_path(workspace)
    root.mkdir(parents=True, exist_ok=True)

    for name in _TEMPLATE_SUBDIRS:
        src = _DATA_DIR / name
        dst = root / name
        if src.is_dir() and not dst.exists():
            shutil.copytree(src, dst)

    return root


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
