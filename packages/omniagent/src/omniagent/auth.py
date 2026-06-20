"""Aegra 鉴权:内网网关注入的 ``X-User-Id`` → ``{identity}``(无租户)。

Aegra 据 ``identity`` 把 thread / run 按用户私有;公网暴露时改为校验 JWT。
"""

from __future__ import annotations

from langgraph_sdk import Auth

auth = Auth()


def resolve_identity(headers: dict[str, str]) -> dict[str, str]:
    """请求头 → ``{identity}``;缺失回退匿名。"""
    return {"identity": headers.get("x-user-id") or "anonymous"}


@auth.authenticate
async def authenticate(headers: dict[str, str]) -> dict[str, str]:
    return resolve_identity(headers)
