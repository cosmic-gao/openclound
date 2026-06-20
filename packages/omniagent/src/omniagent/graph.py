"""Aegra 部署入口:async 工厂图,按 ``(tenant, agent, 配置)`` 装配并缓存编译图。

Aegra 通过 ``aegra.json`` 的 ``graphs`` 注册本模块的 :func:`graph`,识别为 config 工厂、
每请求 ``await`` 调用。assistant backend root = ``<base>/tenant-<id>/assistant-<id>``
(skill 在其下 ``/skills``);同一 assistant 的用户共享该图与文件区,会话历史由 Aegra 按用户
私有。``tenant`` 只取自 ``langgraph_auth_user``(防伪造),无鉴权才回退 ``configurable``。
持久化由 Aegra 注入,故不带 checkpointer / store。
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Any

from omniagent.builder import build_agent
from omniagent.config import AgentConfig, get_settings, safe_segment
from omniagent.mcp import load_mcp_tools
from omniagent.modes import fingerprint, resolve
from omniagent.workspace import agent_root, skill_sources

#: 编译图缓存(键 = ``(tenant, agent, 配置指纹)``);async 构建含 ``await``,故手写
#: ``OrderedDict`` + 锁(FIFO 淘汰),替代不支持协程的 ``lru_cache``。
_CACHE: OrderedDict[tuple[str, str, str], Any] = OrderedDict()
_CACHE_MAX = 256
_LOCK = asyncio.Lock()


def _resolve_scope(config: dict[str, Any] | None) -> tuple[str, str]:
    """解析 ``(tenant, agent)`` 并校验路径段。"""
    cfg = (config or {}).get("configurable") or {}
    auth_user = cfg.get("langgraph_auth_user")
    tenant = (
        getattr(auth_user, "tenant", None) if auth_user else cfg.get("tenant")
    ) or "public"
    agent = cfg.get("agent") or "default"
    return safe_segment(str(tenant)), safe_segment(str(agent))


async def graph(config: dict[str, Any] | None = None) -> Any:
    """Aegra 按请求 async 图工厂。

    Args:
        config: run 配置;``configurable`` 带鉴权用户与开关。本地直调可省略
            (回退 ``public/default`` + react)。
    """
    tenant, agent = _resolve_scope(config)
    settings = get_settings()
    resolved = resolve(AgentConfig.parse((config or {}).get("configurable")), settings)
    key = (tenant, agent, fingerprint(resolved))

    if (cached := _CACHE.get(key)) is not None:
        return cached

    async with _LOCK:
        if (cached := _CACHE.get(key)) is not None:  # 双重检查:等锁期间或已建好
            return cached
        root = agent_root(settings.workspace, tenant, agent)
        tools = await load_mcp_tools(resolved.mcp_servers)
        built = build_agent(
            resolved=resolved,
            workspace=str(root),
            skill_sources=skill_sources(root),
            settings=settings,
            tools=tools,
        )
        _CACHE[key] = built
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)  # FIFO 淘汰最旧
        return built
