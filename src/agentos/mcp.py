"""加载 per-agent MCP 工具,逐 server 容错(单 server 失败仅 warning 跳过,不拖垮其余)。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from langchain_mcp_adapters.client import MultiServerMCPClient

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


async def load_mcp_tools(servers: dict[str, dict[str, Any]]) -> list[BaseTool]:
    """逐 server 异步加载 MCP 工具(失败跳过);工具名以 server 名为前缀。"""
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
