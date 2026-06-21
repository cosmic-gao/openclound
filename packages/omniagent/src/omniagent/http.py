"""skill / agent 资源管理路由(挂 ``aegra.json`` 的 ``http.app``,按 agent 单维)。

各路由用 ``AuthenticatedUser`` 确保已认证(Aegra custom routes 默认不鉴权)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aegra_api.core.auth_deps import AuthenticatedUser
from fastapi import FastAPI, HTTPException, Request

from omniagent import workspace
from omniagent.config import get_settings

app = FastAPI(title="omniagent admin")


def _root(agent: str) -> Path:
    return workspace.agent_root(get_settings().workspace, agent)


@app.get("/skills", tags=["Skill"])
def list_skills(user: AuthenticatedUser, agent: str = "default") -> list[str]:
    return workspace.list_skills(_root(agent))


@app.put("/skills/{name}", tags=["Skill"])
async def put_skill(
    name: str, request: Request, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, Any]:
    body = await request.json()
    files = body.get("files") if isinstance(body, dict) else None
    if not isinstance(files, dict) or not files:
        raise HTTPException(status_code=400, detail='body must be {"files": {...}}')
    try:
        path = workspace.save_skill(_root(agent), name, files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": name, "path": str(path)}


@app.delete("/skills/{name}", tags=["Skill"])
def delete_skill(
    name: str, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, str]:
    try:
        ok = workspace.delete_skill(_root(agent), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"deleted": name}


@app.delete("/agents/{agent}", tags=["Agent"])
def purge(agent: str, user: AuthenticatedUser) -> dict[str, bool]:
    return {"purged": workspace.purge_agent(_root(agent))}
