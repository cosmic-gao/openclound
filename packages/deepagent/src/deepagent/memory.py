"""持久化层:短期记忆(checkpointer)与长期记忆(store)。

- **短期**:``checkpointer`` —— 同一 ``thread_id`` 内的跨轮次记忆,也是
  HITL(人工中断/恢复)的前提。
- **长期**:``store`` —— 跨 thread / 会话的持久键值存储。
- 配合 ``create_deep_agent(memory=[...])`` 读取 ``AGENTS.md`` 注入系统提示
  (见 :mod:`deepagent.agent`)。

这里给的是 **进程内** 实现(``InMemorySaver`` / ``InMemoryStore``),适合
开发、测试与单进程 CLI。生产环境可替换为 ``SqliteSaver`` / Postgres 等,
或交给部署平台(如 LangGraph Platform / Aegra)在运行时注入持久层。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.store.base import BaseStore


def build_checkpointer() -> BaseCheckpointSaver[Any]:
    """构建进程内短期记忆(checkpointer)。"""
    return InMemorySaver()


def build_store() -> BaseStore:
    """构建进程内长期记忆(store)。"""
    return InMemoryStore()
