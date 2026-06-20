"""Aegra 鉴权:内网网关注入的请求头 → ``{identity, tenant}``。

Aegra 仅内网部署,网络隔离即信任边界:直接读 ``X-User-Id`` / ``X-Tenant-Id``,无需守门
密钥。运行身份 ``identity`` = 用户(thread/run 私有),管理身份 ``identity`` = 租户
(assistant 租户级)。公网暴露时改为校验 ``Authorization: Bearer <JWT>``。
"""

from __future__ import annotations

from langgraph_sdk import Auth

auth = Auth()


def resolve_identity(headers: dict[str, str]) -> dict[str, str]:
    """请求头 → ``{identity, tenant}``;缺失回退匿名 + ``public``。"""
    return {
        "identity": headers.get("x-user-id") or "anonymous",
        "tenant": headers.get("x-tenant-id") or "public",
    }


@auth.authenticate
async def authenticate(headers: dict[str, str]) -> dict[str, str]:
    return resolve_identity(headers)
