"""加载 MCP server 工具(逐 server 容错)。

基于 ``langchain-mcp-adapters``;其工具每次调用新建临时会话(无需关闭),但多 server 加载
无异常隔离,故本模块逐 server 加载:失败仅记 warning 跳过,不拖垮其余工具。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from langchain_mcp_adapters.client import MultiServerMCPClient

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


async def load_mcp_tools(servers: dict[str, dict[str, Any]]) -> list[BaseTool]:
    """逐 server 异步加载 MCP 工具,单 server 失败仅跳过;工具名以 server 名为前缀。"""
    if not servers:
        return []

    client = MultiServerMCPClient(cast("Any", servers), tool_name_prefix=True)
    names = list(servers)
    results = await asyncio.gather(
        *(client.get_tools(server_name=name) for name in names),
        return_exceptions=True,
    )
    tools: list[BaseTool] = []
    for name, result in zip(names, results, strict=True):
        if isinstance(result, BaseException):
            logger.warning("MCP server %r failed to load, skipping: %s", name, result)
            continue
        tools.extend(result)
    return tools
