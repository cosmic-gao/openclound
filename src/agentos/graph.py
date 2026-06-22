"""Aegra 部署入口:async 工厂图,按 ``(agent, 配置+skill 指纹)`` 缓存编译图。

图不带 checkpointer / store(平台注入);scope 仅 agent(无租户),鉴权交平台(默认 noop)。
"""

from __future__ import annotations

import asyncio
from typing import Any
from weakref import WeakValueDictionary

from cachetools import TTLCache

from agentos.builder import build_agent
from agentos.config import AgentConfig, fingerprint, get_settings, resolve, safe_segment
from agentos.mcp import load_mcp_tools
from agentos.storage import agent_root, skill_signature, skill_sources

#: 编译图缓存(LRU+TTL;键含 skill 签名,故 skill 增删触发重建)。
_CACHE: TTLCache[tuple[str, str], Any] = TTLCache(maxsize=256, ttl=3600)
#: per-key 锁(singleflight):同 key 并发构建去重。
_LOCKS: WeakValueDictionary[tuple[str, str], asyncio.Lock] = WeakValueDictionary()


def _configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    """取 ``config.configurable``(Agent Protocol 标准结构)。"""
    return (config or {}).get("configurable") or {}


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
