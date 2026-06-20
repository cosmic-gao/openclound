"""Aegra 部署入口:async 工厂图,按 ``(agent, 配置 + skill 指纹)`` 装配并缓存编译图。

每请求 ``await`` 调用;图不带 checkpointer / store(平台注入)。无租户:scope 仅 agent,
backend root = ``<workspace>/<agent>``,会话历史由 Aegra 按用户私有。
"""

from __future__ import annotations

import asyncio
from typing import Any
from weakref import WeakValueDictionary

from cachetools import TTLCache

from omniagent.builder import build_agent
from omniagent.config import AgentConfig, get_settings, safe_segment
from omniagent.mcp import load_mcp_tools
from omniagent.resolve import fingerprint, resolve
from omniagent.workspace import agent_root, skill_signature, skill_sources

#: 编译图缓存(键 = (agent, 指纹);LRU + TTL)。指纹含 skill 签名,故 skill 增删触发重建。
_CACHE: TTLCache[tuple[str, str], Any] = TTLCache(maxsize=256, ttl=3600)
#: per-key 锁(singleflight):同 key 并发构建去重,不同 agent 冷启动互不阻塞。
_LOCKS: WeakValueDictionary[tuple[str, str], asyncio.Lock] = WeakValueDictionary()


def _configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    """兼容标准 ``config.configurable`` 与扁平 ``config`` 顶层(后者运行时注入优先)。"""
    config = config or {}
    return {**config, **(config.get("configurable") or {})}


def _resolve_scope(config: dict[str, Any] | None) -> str:
    """解析并校验 ``agent``;缺省回退 ``assistant_id``,再回退 ``default``。"""
    cfg = _configurable(config)
    agent = cfg.get("agent") or cfg.get("assistant_id") or "default"
    return safe_segment(str(agent))


def _lock_for(key: tuple[str, str]) -> asyncio.Lock:
    lock = _LOCKS.get(key)
    if lock is None:
        lock = _LOCKS.setdefault(key, asyncio.Lock())
    return lock


async def graph(config: dict[str, Any] | None = None) -> Any:
    """Aegra 按请求 async 图工厂(按 agent + 配置 / skill 指纹缓存)。"""
    agent = _resolve_scope(config)
    settings = get_settings()
    resolved = resolve(AgentConfig.parse(_configurable(config)), settings)
    root = agent_root(settings.workspace, agent)
    key = (agent, fingerprint(resolved, skill_signature(root)))

    if (cached := _CACHE.get(key)) is not None:
        return cached
    async with _lock_for(key):
        if (cached := _CACHE.get(key)) is not None:  # 双检:等锁期间可能已建好
            return cached
        tools = await load_mcp_tools(resolved.mcp_servers)
        built = build_agent(
            resolved=resolved,
            workspace=str(root),
            skill_sources=skill_sources(root),
            agent=agent,
            settings=settings,
            tools=tools,
        )
        _CACHE[key] = built
        return built
