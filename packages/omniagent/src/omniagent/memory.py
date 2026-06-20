"""跨会话持久记忆(opt-in):``/memories`` 路由到平台 store,按 assistant 命名空间隔离。

``memory`` 开 → ``CompositeBackend``(默认本地 + ``/memories``→``StoreBackend``);
``StoreBackend`` 运行时经 ``get_store()`` 取 Aegra 注入的 store,故图编译期不带 store。
``memory`` 关 → 纯本地 backend(无 store 依赖)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepagents.backends import (
    BackendProtocol,
    CompositeBackend,
    FilesystemBackend,
    LocalShellBackend,
    StoreBackend,
)

if TYPE_CHECKING:
    from pathlib import Path

    from omniagent.resolve import ResolvedConfig

MEMORY_ROUTE = "/memories/"
MEMORY_FILE = "/memories/AGENTS.md"


def _local_backend(
    resolved: ResolvedConfig, root: Path
) -> FilesystemBackend | LocalShellBackend:
    """``execute`` 未裁剪 → 跨平台 shell backend,否则纯文件 backend(均虚拟根沙箱化)。"""
    if "execute" in resolved.excluded_tools:
        return FilesystemBackend(root_dir=root, virtual_mode=True)
    return LocalShellBackend(root_dir=root, virtual_mode=True, inherit_env=True)


def build_backend(resolved: ResolvedConfig, root: Path, agent: str) -> BackendProtocol:
    """``memory`` 关 → 本地 backend;开 → Composite(默认本地 + ``/memories``→store)。"""
    local = _local_backend(resolved, root)
    if not resolved.memory:
        return local

    def _namespace(_runtime: Any) -> tuple[str, ...]:
        return ("memories", agent)

    store = StoreBackend(namespace=_namespace)
    return CompositeBackend(default=local, routes={MEMORY_ROUTE: store})


def memory_sources(resolved: ResolvedConfig) -> list[str] | None:
    """``memory`` 开 → ``[MEMORY_FILE]``(供 ``MemoryMiddleware``);否则 ``None``。"""
    return [MEMORY_FILE] if resolved.memory else None
