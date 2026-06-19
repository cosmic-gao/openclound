"""MCP 工具加载:把 MCP server 暴露的工具加载为 LangChain 工具。

基于 ``langchain-mcp-adapters`` 的 ``MultiServerMCPClient``,加载结果可直接传给
:func:`deepagent.agent.build_agent` 的 ``tools`` 参数,或经由
:func:`deepagent.agent.build_async_agent` 的 ``mcp_servers`` 参数自动加载。

MCP 连接是异步的,因此本模块的入口为 ``async``。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


async def load_mcp_tools(servers: dict[str, dict[str, Any]]) -> list[BaseTool]:
    """从一组 MCP server 异步加载工具。

    Args:
        servers: ``MultiServerMCPClient`` 的连接配置,键为 server 名,值为连接
            参数。例如::

                {
                    "weather": {
                        "transport": "streamable_http",
                        "url": "http://localhost:8000/mcp",
                    },
                    "fs": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["server.py"],
                    },
                }

    Returns:
        可直接交给 agent 的 LangChain 工具列表;``servers`` 为空时返回空列表。
    """
    if not servers:
        return []

    # 延迟导入:仅在真正使用 MCP 时才要求安装 langchain-mcp-adapters。
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(cast("Any", servers), tool_name_prefix=True)
    return await client.get_tools()
