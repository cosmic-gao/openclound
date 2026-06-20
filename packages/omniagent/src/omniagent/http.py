"""skill / agent 资源管理路由(挂 ``aegra.json`` 的 ``http.app``)。

Aegra custom routes 默认不鉴权,故各路由用 ``AuthenticatedUser`` 注入鉴权用户(走
:mod:`omniagent.auth`),租户取自其 ``tenant``。

- ``GET/PUT/DELETE /skills?agent=<id>`` — 该 agent 的 skill 增删查
- ``DELETE /agents/{agent}`` — 删该 agent 的 backend root(skill + 运行期文件)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegra_api.core.auth_deps import AuthenticatedUser
from aegra_api.models.auth import User
from fastapi import FastAPI, HTTPException, Request

from omniagent import skills
from omniagent.config import get_settings
from omniagent.workspace import agent_root, purge_agent

app = FastAPI(title="omniagent admin")


def _root(user: User, agent: str) -> Path:
    """鉴权用户租户下该 agent 的 backend root。"""
    tenant = str(getattr(user, "tenant", None) or "public")
    return agent_root(get_settings().workspace, tenant, agent)


@app.get("/skills")
def list_skills(user: AuthenticatedUser, agent: str = "default") -> list[str]:
    return skills.list_skills(_root(user, agent))


@app.put("/skills/{name}")
async def put_skill(
    name: str, request: Request, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, Any]:
    body = await request.json()
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, dict) or not files:
        raise HTTPException(status_code=400, detail='body must be {"files": {...}}')
    try:
        path = skills.save_skill(_root(user, agent), name, files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": name, "path": str(path)}


@app.delete("/skills/{name}")
def delete_skill(
    name: str, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, str]:
    try:
        ok = skills.delete_skill(_root(user, agent), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"deleted": name}


@app.delete("/agents/{agent}")
def purge(agent: str, user: AuthenticatedUser) -> dict[str, bool]:
    """删该 agent 的 backend root(skill + 运行期文件)。"""
    return {"purged": purge_agent(_root(user, agent))}
