"""Aegra 鉴权:把请求身份解析为 ``{用户, 租户}`` 两个维度。

Aegra 通过 ``aegra.json`` 的 ``auth.path`` 加载本模块的 ``auth``(一个
``langgraph_sdk.Auth`` 实例)。``@auth.authenticate`` 收到 **已解码、键名小写** 的请求头
dict,返回的 dict 至少含 ``identity``;额外字段(此处 ``tenant_id``)会随鉴权用户一并
传到图工厂 :func:`omniagent.graph.graph`。

两个维度对应两套正交隔离:

- ``identity`` = **用户**。Aegra 把 assistant / thread / run / cron 全部按
  ``user_id == identity`` 强隔离,故 identity 即「每个用户私有自己的 agent 与会话」;
  identity 须全局唯一(跨租户)。
- ``tenant_id`` = **租户**。Aegra 不认它;omniagent 用它定位 **租户共享的 skill**
  与按用户隔离的工作区(见 :mod:`omniagent.graph`)。

身份来源(按优先级):

1. ``Authorization: Bearer <token>``——**生产**应在此校验 token 并从 claims 解析出
   ``identity`` 与 ``tenant_id``;当前为占位(把 token 当 identity、租户落 ``public``),
   请接入你的 IdP / JWT 校验。
2. ``X-User-Id`` / ``X-Tenant-Id`` 头——**仅本地联调**(配合 agent-chat-ui 的 User /
   Tenant 输入),明文、无校验。仅当 ``AGENT_DEV_AUTH`` 开启时才信任,默认关闭。

二者都不满足时回退匿名用户 + ``public`` 租户(开箱即用,等价 noop)。未配置本模块
(``aegra.json`` 不写 ``auth.path``)时,Aegra 自身的 noop 鉴权同样落 ``public``。
"""

from __future__ import annotations

import os

from langgraph_sdk import Auth

auth = Auth()

# 仅本地联调:置 1/true/yes 才信任明文 X-User-Id / X-Tenant-Id 头(无校验);默认关闭,
# 确保误上生产时不会因一个请求头就冒充任意用户 / 租户。
DEV_AUTH = os.getenv("AGENT_DEV_AUTH", "").strip().lower() in ("1", "true", "yes")


def resolve_identity(
    headers: dict[str, str], *, dev_auth: bool = DEV_AUTH
) -> dict[str, str]:
    """从请求头解析 ``{"identity", "tenant_id"}``(纯函数,便于测试)。"""
    token = headers.get("authorization", "")
    if token[:7].lower() == "bearer ":
        # 生产占位:此处应校验 token 并从 claims 取用户与租户。
        subject = token[7:].strip() or "anonymous"
        return {"identity": subject, "tenant_id": "public"}

    if dev_auth:
        # 本地联调:信任明文 X-User-Id / X-Tenant-Id(无校验)。
        return {
            "identity": headers.get("x-user-id") or "anonymous",
            "tenant_id": headers.get("x-tenant-id") or "public",
        }

    # 无凭证:匿名用户,落共享 public 租户(开箱即用,等价 noop)。
    return {"identity": "anonymous", "tenant_id": "public"}


@auth.authenticate
async def authenticate(headers: dict[str, str]) -> dict[str, str]:
    """Aegra 鉴权入口:委托 :func:`resolve_identity`。"""
    return resolve_identity(headers)
