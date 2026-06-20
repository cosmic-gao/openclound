"""skill / agent 资源管理路由(挂 ``aegra.json`` 的 ``http.app``)。

Aegra custom routes 默认不鉴权,故各路由用 ``AuthenticatedUser`` 注入鉴权用户(走
:mod:`omniagent.auth`),租户取自其 ``tenant``。

- ``GET/PUT/DELETE /skills?agent=<id>`` — agent skill 增删查
- ``DELETE /agents/{agent}`` — 清该 agent 的 skill + 各用户工作目录
"""

from __future__ import annotations

from typing import Any

from aegra_api.core.auth_deps import AuthenticatedUser
from aegra_api.models.auth import User
from fastapi import FastAPI, HTTPException, Request

from omniagent import skills
from omniagent.config import get_settings
from omniagent.workspace import purge_agent

app = FastAPI(title="omniagent admin")


def _tenant(user: User) -> str:
    return str(getattr(user, "tenant", None) or "public")


@app.get("/skills")
def list_skills(user: AuthenticatedUser, agent: str = "default") -> list[str]:
    return skills.list_skills(get_settings().skills_root, _tenant(user), agent)


@app.put("/skills/{name}")
async def put_skill(
    name: str, request: Request, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, Any]:
    body = await request.json()
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, dict) or not files:
        raise HTTPException(status_code=400, detail='body must be {"files": {...}}')
    try:
        path = skills.save_skill(
            get_settings().skills_root, _tenant(user), agent, name, files
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": name, "path": str(path)}


@app.delete("/skills/{name}")
def delete_skill(
    name: str, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, str]:
    try:
        ok = skills.delete_skill(get_settings().skills_root, _tenant(user), agent, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"deleted": name}


@app.delete("/agents/{agent}")
def purge(agent: str, user: AuthenticatedUser) -> dict[str, bool]:
    """清该 agent 的 skill 目录 + 各用户工作目录(网关删 assistant 后调用)。"""
    settings = get_settings()
    try:
        return purge_agent(
            settings.skills_root, settings.workspace, _tenant(user), agent
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
