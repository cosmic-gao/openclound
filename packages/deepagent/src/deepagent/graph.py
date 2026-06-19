"""Aegra 部署入口:把 deepagent 暴露为 Aegra 可加载的「图」。

`Aegra <https://docs.aegra.dev>`_(自托管的 LangGraph Platform 替代,FastAPI + Postgres)
通过 ``aegra.json`` 的 ``graphs`` 注册图,值形如 ``"./src/deepagent/graph.py:graph"``。
本模块导出一个 0 参工厂 :func:`graph`,Aegra 在启动时调用一次并缓存结果。

持久化(线程 / 运行 / 状态)由 Aegra 用 Postgres 自动注入(见 ``build_agent``
的 ``platform_managed=True``),因此这里**不**配置任何 checkpointer / store。

需要挂载 MCP 工具时,可改用异步工厂(Aegra 同样支持),例如::

    import json
    import os
    from contextlib import asynccontextmanager
    from deepagent.agent import build_async_agent

    @asynccontextmanager
    async def graph(config):
        servers = json.loads(os.getenv("AGENT_MCP_SERVERS", "{}"))
        yield await build_async_agent(mcp_servers=servers, platform_managed=True)

并把 ``aegra.json`` 指向该异步工厂即可。
"""

from __future__ import annotations

from typing import Any

from deepagent.agent import build_agent


def graph() -> Any:
    """Aegra 图工厂:构建由平台托管持久化的 deep agent(启动时调用一次)。

    模型 / 工具 / skills / memory / 中间件等均按环境变量(``AGENT_*`` 或 ``.env``)
    配置。持久化交给 Aegra,故不带 checkpointer / store。
    """
    return build_agent(platform_managed=True)
