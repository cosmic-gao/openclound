"""skill 管理 HTTP 入口:挂到 Aegra ``aegra.json`` 的 ``http.app``。

提供按**租户**在线增删查共享 skill 的接口;写入磁盘后,下一个新会话即热加载(无需
重启)。依赖 ``fastapi``(Aegra 运行时自带;本包仅在 ``--extra aegra`` 下安装)。

接到 Aegra::

    // aegra.json
    "http": { "app": "./src/omniagent/http.py:app" }

路由(租户取自鉴权身份):

- ``GET /skills`` — 列出公有 + 该租户共享 skill
- ``PUT /skills/{name}`` — 写入/覆盖租户 skill(body ``{"files": {...}}``)
- ``DELETE /skills/{name}`` — 删除租户 skill

agent(assistant)的注册 / 列表 / 删除 / 在线状态请用 **Aegra 原生** ``/assistants``
(按 ``user_id == identity`` 私有于用户):

- ``GET /assistants`` 列表 · ``GET /assistants/{id}`` 查存在(即"可用")
- ``DELETE /assistants/{id}`` 删记录 —— 之后调
  :func:`omniagent.workspace.purge_agent` 清该用户该 agent 的工作目录。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from omniagent import skills
from omniagent.config import get_settings
from omniagent.workspace import seed_public_skills

app = FastAPI(title="omniagent skill admin")


def _tenant(request: Request) -> str:
    """从鉴权身份取租户(skill 的共享边界)。

    生产取自 Aegra 鉴权身份(``request.scope["user"]`` 是 ``User`` 对象)的 ``tenant_id``,
    与 ``graph.py`` 的解析保持一致;此处兜底读 ``X-Tenant-Id`` 头,便于本地联调。
    """
    user = request.scope.get("user")
    # User.__getattr__ 对缺失字段抛 AttributeError,故用带默认值的 getattr。
    tenant = getattr(user, "tenant_id", None) if user is not None else None
    return str(tenant or request.headers.get("x-tenant-id") or "public")


@app.get("/skills")
def list_skills(request: Request) -> dict[str, list[str]]:
    settings = get_settings()
    seed_public_skills(settings.skills_root)  # 确保公有 skill 已就绪(便于初次查询可见)
    return skills.list_skills(settings.skills_root, _tenant(request))


@app.put("/skills/{name}")
async def put_skill(request: Request, name: str) -> dict[str, Any]:
    body = await request.json()
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, dict) or not files:
        raise HTTPException(status_code=400, detail='body must be {"files": {...}}')
    settings = get_settings()
    try:
        path = skills.save_skill(settings.skills_root, _tenant(request), name, files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": name, "path": str(path)}


@app.delete("/skills/{name}")
def delete_skill(request: Request, name: str) -> dict[str, str]:
    settings = get_settings()
    try:
        ok = skills.delete_skill(settings.skills_root, _tenant(request), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"deleted": name}
