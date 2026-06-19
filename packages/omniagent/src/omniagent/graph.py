"""Aegra 部署入口:把 agent 暴露为 Aegra 可加载的「图」(多用户 / 多 agent / 多租户)。

`Aegra <https://docs.aegra.dev>`_(自托管 LangGraph Platform 替代,FastAPI + Postgres)
通过 ``aegra.json`` 的 ``graphs`` 注册图,值形如 ``"./src/omniagent/graph.py:graph"``。

本模块导出一个 **按请求构建的工厂** :func:`graph`。每次 run 从 ``config`` 解析出三个
维度,对应两套正交的隔离:

- **user**:取自鉴权身份 ``langgraph_auth_user.identity``。Aegra 把 assistant /
  thread / run / cron 按 ``user_id == identity`` 强隔离,即每个用户私有自己的 agent
  与会话;omniagent 据此把工作区也按用户私有。
- **tenant**:取自鉴权身份的自定义字段 ``tenant_id``(见 :mod:`omniagent.auth`)。Aegra
  不认它;omniagent 用它定位 **租户共享的 skill**(同租户所有用户 / agent 共享)。
- **agent**:取自 assistant 配置 ``configurable.agent_id``,其 ``system_prompt`` 即该
  agent 的场景指令。

据此:skill 源 = ``[公有, 该租户]``(租户共享 + 全局 public);工作区 =
``work/<tenant>/<user>/<agent>``(用户私有)。持久化由 Aegra 注入(Postgres),故
``platform_managed=True``、不带 checkpointer / store;skill 改动下个新会话生效。

安全:有鉴权身份时 user / tenant 只取自 ``langgraph_auth_user``,
不信客户端 ``configurable``(防伪造);无鉴权(本地直调)才回退 config。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from omniagent.builder import DEFAULT_SYSTEM_PROMPT, build_agent
from omniagent.config import get_settings, safe_segment
from omniagent.workspace import skill_sources


def _resolve_scope(config: dict[str, Any] | None) -> tuple[str, str, str, str]:
    """从 run config 解析 ``(user, tenant, agent, system_prompt)``,并校验路径段。"""
    cfg = (config or {}).get("configurable") or {}
    auth_user = cfg.get("langgraph_auth_user")
    if auth_user is not None:
        # 鉴权身份(Aegra ``User`` 对象):identity=用户(Aegra 隔离锚),tenant_id=租户。
        # ``User.__getattr__`` 对缺失字段抛 AttributeError,故用带默认值的 getattr。
        user = getattr(auth_user, "identity", None) or "anonymous"
        tenant = getattr(auth_user, "tenant_id", None) or "public"
    else:
        # 本地直调(无鉴权):从 configurable 回退。
        user = cfg.get("user_id") or "anonymous"
        tenant = cfg.get("tenant_id") or "public"
    agent = cfg.get("agent_id") or "default"
    system_prompt = cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    return (
        safe_segment(str(user)),
        safe_segment(str(tenant)),
        safe_segment(str(agent)),
        system_prompt,
    )


@lru_cache(maxsize=256)
def _build_agent(user: str, tenant: str, agent: str, system_prompt: str) -> Any:
    """按 ``(user, tenant, agent, system_prompt)`` 构建并缓存编译图。

    缓存的是**编译图**(避免每条消息重编译);skill 仍在 ``before_agent`` 运行时按会话
    重扫,故热更新不受缓存影响。模型 / skills_root 等来自环境(进程内固定),变更后需
    重启或 ``_build_agent.cache_clear()``。
    """
    settings = get_settings()
    # skill:公有 + 租户共享(同租户所有用户 / agent 共享)。
    sources = skill_sources(settings.skills_root, tenant)
    # 工作区:按 (租户, 用户, agent) 私有(execute cwd + 会话文件,用户间不串)。
    settings.workspace = str(Path(settings.workspace) / "work" / tenant / user / agent)
    return build_agent(
        settings=settings,
        skill_sources=sources,
        system_prompt=system_prompt,
        platform_managed=True,
    )


def graph(config: dict[str, Any] | None = None) -> Any:
    """Aegra 按请求图工厂:按 ``(user, tenant, agent)`` 装配 skill 与场景(图带缓存)。

    Args:
        config: Aegra/LangGraph 传入的 run 配置;``configurable`` 里带鉴权用户与
            assistant 配置。本地直接调用时可省略(回退 ``anonymous/public/default``)。
    """
    return _build_agent(*_resolve_scope(config))
