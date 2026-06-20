"""Aegra 部署入口:async 工厂图,按 ``(scope, 配置)`` 装配并缓存编译图。

Aegra 通过 ``aegra.json`` 的 ``graphs`` 注册本模块的 :func:`graph`,识别为 config 工厂、
每请求 ``await`` 调用。每次 run 从 ``config`` 解析 scope(user/tenant/agent)与
``AgentConfig``,合并出开关,装配 skill / 工作区 / 模型 / 工具 / 审核。

scope 中 user / tenant **只取自** ``langgraph_auth_user``(防伪造);无鉴权才回退
``configurable``。图按 ``(scope, 配置指纹)`` 缓存;持久化由 Aegra 注入,故不带
checkpointer / store。
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from pathlib import Path
from typing import Any

from omniagent.builder import build_agent
from omniagent.config import AgentConfig, get_settings, safe_segment
from omniagent.mcp import load_mcp_tools
from omniagent.modes import fingerprint, resolve
from omniagent.workspace import skill_sources

#: 编译图缓存(键 = ``(user, tenant, agent, 配置指纹)``);async 构建含 ``await``,故手写
#: ``OrderedDict`` + 锁(FIFO 淘汰),替代不支持协程的 ``lru_cache``。
_CACHE: OrderedDict[tuple[str, str, str, str], Any] = OrderedDict()
_CACHE_MAX = 256
_LOCK = asyncio.Lock()


def _resolve_scope(config: dict[str, Any] | None) -> tuple[str, str, str]:
    """解析 ``(user, tenant, agent)`` 并校验路径段。"""
    cfg = (config or {}).get("configurable") or {}
    auth_user = cfg.get("langgraph_auth_user")
    if auth_user is not None:
        user = getattr(auth_user, "identity", None) or "anonymous"
        tenant = getattr(auth_user, "tenant", None) or "public"
    else:
        user = cfg.get("user_id") or "anonymous"
        tenant = cfg.get("tenant") or "public"
    agent = cfg.get("agent") or "default"
    return safe_segment(str(user)), safe_segment(str(tenant)), safe_segment(str(agent))


async def graph(config: dict[str, Any] | None = None) -> Any:
    """Aegra 按请求 async 图工厂。

    Args:
        config: run 配置;``configurable`` 带鉴权用户与开关。本地直调可省略
            (回退 ``anonymous/public/default`` + react)。
    """
    user, tenant, agent = _resolve_scope(config)
    settings = get_settings()
    resolved = resolve(AgentConfig.parse((config or {}).get("configurable")), settings)
    key = (user, tenant, agent, fingerprint(resolved))

    if (cached := _CACHE.get(key)) is not None:
        return cached

    async with _LOCK:
        if (cached := _CACHE.get(key)) is not None:  # 双重检查:等锁期间或已建好
            return cached
        tools = await load_mcp_tools(resolved.mcp_servers)
        built = build_agent(
            resolved=resolved,
            skill_sources=skill_sources(settings.skills_root, tenant, agent),
            workspace=str(Path(settings.workspace) / "work" / tenant / user / agent),
            settings=settings,
            tools=tools,
        )
        _CACHE[key] = built
        if len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)  # FIFO 淘汰最旧
        return built
