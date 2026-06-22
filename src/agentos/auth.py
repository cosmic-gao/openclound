"""Aegra 鉴权(custom):从请求头取 x-tenant-id / x-user-id 作 identity(内网信任,不校验)。"""

from __future__ import annotations

from langgraph_sdk import Auth

auth = Auth()


@auth.authenticate
async def authenticate(headers: dict[str, str]) -> dict[str, str]:
    """读 x-tenant-id / x-user-id;identity=``tenant_id:user_id``,tenant_id/user_id 透出。"""
    tenant_id = headers.get("x-tenant-id") or "default"
    user_id = headers.get("x-user-id") or "anonymous"
    return {
        "identity": f"{tenant_id}:{user_id}",
        "tenant_id": tenant_id,
        "user_id": user_id,
    }
