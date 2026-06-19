"""skill 管理 HTTP 入口:挂到 Aegra ``aegra.json`` 的 ``http.app``。

提供租户为某 agent 在线增删查私有 skill 的接口;写入磁盘后,下一个新会话即热加载
(无需重启)。依赖 ``fastapi``(Aegra 运行时自带;本包仅在 ``--extra aegra`` 下安装)。

接到 Aegra::

    // aegra.json
    "http": { "app": "./src/agent/http.py:app" }

路由(``agent_id`` 经查询参数;租户取自鉴权):

skill(私有 skill 增删查):

- ``GET /skills`` — 列出公有 + 该 (租户,agent) 私有 skill
- ``PUT /skills/{name}`` — 写入/覆盖私有 skill(body ``{"files": {...}}``)
- ``DELETE /skills/{name}`` — 删除私有 skill

agent 的注册 / 列表 / 删除 / 在线状态请用 **Aegra 原生** ``/assistants``:

- ``GET /assistants`` 列表 · ``POST /assistants/search`` 按租户过滤
- ``GET /assistants/{id}`` 查存在(即"可用")· ``DELETE /assistants/{id}`` 删记录

删 agent 后记得调 :func:`omniagent.workspace.purge_agent` 清理我方 skill / 工作目录。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from omniagent import skills
from omniagent.config import get_settings
from omniagent.workspace import seed_public_skills

app = FastAPI(title="agent agent/skill admin")


def _tenant(request: Request) -> str:
    """从请求解析租户。

    生产应取自 Aegra 鉴权身份(``request.scope["user"]`` 是 ``User`` 对象);租户优先
    ``tenant_id``、回退一等字段 ``org_id``,与 ``graph.py`` 的解析保持一致。此处兜底读
    ``X-Tenant-Id`` 头,便于本地联调。按你的 Aegra auth 方案调整这一处即可。
    """
    user = request.scope.get("user")
    tenant = None
    if user is not None:
        # User.__getattr__ 对缺失字段抛 AttributeError,故用带默认值的 getattr。
        tenant = getattr(user, "tenant_id", None) or getattr(user, "org_id", None)
    return str(tenant or request.headers.get("x-tenant-id") or "public")


@app.get("/skills")
def list_skills(request: Request, agent_id: str = "default") -> dict[str, list[str]]:
    settings = get_settings()
    seed_public_skills(settings.skills_root)  # 确保公有 skill 已就绪(便于初次查询可见)
    return skills.list_skills(settings.skills_root, _tenant(request), agent_id)


@app.put("/skills/{name}")
async def put_skill(
    request: Request, name: str, agent_id: str = "default"
) -> dict[str, Any]:
    body = await request.json()
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, dict) or not files:
        raise HTTPException(status_code=400, detail='body must be {"files": {...}}')
    settings = get_settings()
    try:
        path = skills.save_skill(
            settings.skills_root, _tenant(request), agent_id, name, files
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": name, "path": str(path)}


@app.delete("/skills/{name}")
def delete_skill(
    request: Request, name: str, agent_id: str = "default"
) -> dict[str, str]:
    settings = get_settings()
    try:
        ok = skills.delete_skill(settings.skills_root, _tenant(request), agent_id, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"deleted": name}
