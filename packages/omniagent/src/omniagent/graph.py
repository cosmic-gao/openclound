"""Aegra 部署入口:把 agent 暴露为 Aegra 可加载的「图」(多租户 / 多 agent)。

`Aegra <https://docs.aegra.dev>`_(自托管 LangGraph Platform 替代,FastAPI + Postgres)
通过 ``aegra.json`` 的 ``graphs`` 注册图,值形如 ``"./src/agent/graph.py:graph"``。

本模块导出一个 **按请求构建的工厂** :func:`graph`。每次 run 时从 ``config`` 解析出:

- **租户**:取自鉴权身份 ``config["configurable"]["langgraph_auth_user"]``(Aegra 的
  ``User`` 对象;租户优先 ``tenant_id``、回退一等字段 ``org_id``)。安全考量:有鉴权身份
  时只信它;无鉴权(本地 / noop)才回退 ``configurable.tenant_id`` 或 ``"public"``。
- **agent**:取自 assistant 配置 ``configurable.agent_id``(每个 agent = 一个 Aegra
  assistant,带各自场景);其 ``system_prompt`` 作为该 agent 的场景指令。

据此拼出 skill 源 ``[公有, 该租户该 agent 私有]`` 并构建 agent。持久化(线程 / 运行 /
状态)由 Aegra 用 Postgres 注入,故 ``platform_managed=True``、不带 checkpointer / store。
skill 改动写入磁盘后,下一个新会话即热加载。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from omniagent.builder import DEFAULT_SYSTEM_PROMPT, build_agent
from omniagent.config import get_settings, safe_segment
from omniagent.workspace import tenant_skill_sources


def _resolve_tenant_agent(config: dict[str, Any] | None) -> tuple[str, str, str]:
    """从 run config 解析 ``(tenant, agent, system_prompt)``,并校验路径段。

    鉴权身份是 Aegra 的 ``User`` 对象(``aegra_api.models.auth.User``,``extra="allow"``),
    按属性取值;``User.__getattr__`` 对缺失字段抛 ``AttributeError``,故用带默认值的
    ``getattr`` 兜底。
    """
    cfg = (config or {}).get("configurable") or {}
    user = cfg.get("langgraph_auth_user")
    # 有鉴权身份时**只信它**(防客户端用 configurable.tenant_id 伪造):租户优先取
    # ``tenant_id``,回退 Aegra 一等字段 ``org_id``。无鉴权(本地 / noop)才回退 config。
    if user is not None:
        raw = getattr(user, "tenant_id", None) or getattr(user, "org_id", None)
        tenant = str(raw) if raw else "public"
    else:
        tenant = str(cfg.get("tenant_id") or "public")
    agent = str(cfg.get("agent_id") or "default")
    system_prompt = cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    return safe_segment(tenant), safe_segment(agent), system_prompt


@lru_cache(maxsize=128)
def _build_agent(tenant: str, agent: str, system_prompt: str) -> Any:
    """按 ``(tenant, agent, system_prompt)`` 构建并缓存编译图。

    缓存的是**编译图**(避免每条消息重编译);skill 仍在 ``before_agent`` 运行时按
    会话重扫,故热更新不受缓存影响。模型 / 工作区等来自环境(进程内固定),变更后需
    重启或 ``_build_agent.cache_clear()``。
    """
    settings = get_settings()
    sources = tenant_skill_sources(settings.skills_root, tenant, agent)
    # 每个 (租户, agent) 独立工作目录(execute cwd + 会话文件)。
    settings.workspace = str(Path(settings.workspace) / "work" / tenant / agent)
    return build_agent(
        settings=settings,
        skill_sources=sources,
        system_prompt=system_prompt,
        platform_managed=True,
    )


def graph(config: dict[str, Any] | None = None) -> Any:
    """Aegra 按请求图工厂:按 ``(tenant, agent)`` 装配 skill 与场景(编译图带缓存)。

    Args:
        config: Aegra/LangGraph 传入的 run 配置;``configurable`` 里带鉴权用户与
            assistant 配置。本地直接调用时可省略(回退到 ``public/default``)。
    """
    return _build_agent(*_resolve_tenant_agent(config))
