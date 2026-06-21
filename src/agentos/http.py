"""skill / agent 资源管理路由(挂 ``aegra.json`` 的 ``http.app``,按 agent=assistant_id)。

skill 文件级 CRUD:列表 / 读 / 写(新增=保存,不限类型)/ 改名 / 删;另有列 skill、删整个
skill、清 agent。各路由用 ``AuthenticatedUser`` 确保已认证(custom routes 默认不鉴权)。
"""

from __future__ import annotations

from pathlib import Path

from aegra_api.core.auth_deps import AuthenticatedUser
from fastapi import FastAPI, HTTPException, Request

from agentos import storage
from agentos.config import get_settings

app = FastAPI(title="agentos admin")


def _root(agent: str) -> Path:
    return storage.agent_root(get_settings().workspace, agent)


@app.get("/skills", tags=["Skill"])
def list_skills(user: AuthenticatedUser, agent: str = "default") -> list[str]:
    return storage.list_skills(_root(agent))


@app.delete("/skills/{name}", tags=["Skill"])
def delete_skill(
    name: str, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, str]:
    try:
        ok = storage.delete_skill(_root(agent), name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill not found")
    return {"deleted": name}


@app.get("/skills/{name}/files", tags=["Skill"])
def list_skill_files(
    name: str, user: AuthenticatedUser, agent: str = "default"
) -> list[str]:
    return storage.list_skill_files(_root(agent), name)


@app.get("/skills/{name}/files/{path:path}", tags=["Skill"])
def read_skill_file(
    name: str, path: str, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, str]:
    try:
        content = storage.read_skill_file(_root(agent), name, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="skill file not found") from exc
    return {"path": path, "content": content}


@app.put("/skills/{name}/files/{path:path}", tags=["Skill"])
async def write_skill_file(
    name: str,
    path: str,
    request: Request,
    user: AuthenticatedUser,
    agent: str = "default",
) -> dict[str, str]:
    body = await request.json()
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, str):
        raise HTTPException(status_code=400, detail='body must be {"content": "..."}')
    try:
        dest = storage.write_skill_file(_root(agent), name, path, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": path, "path": str(dest)}


@app.patch("/skills/{name}/files/{path:path}", tags=["Skill"])
async def rename_skill_file(
    name: str,
    path: str,
    request: Request,
    user: AuthenticatedUser,
    agent: str = "default",
) -> dict[str, str]:
    body = await request.json()
    to = body.get("to") if isinstance(body, dict) else None
    if not isinstance(to, str) or not to:
        raise HTTPException(status_code=400, detail='body must be {"to": "..."}')
    try:
        dest = storage.rename_skill_file(_root(agent), name, path, to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="skill file not found") from exc
    return {"renamed": path, "to": to, "path": str(dest)}


@app.delete("/skills/{name}/files/{path:path}", tags=["Skill"])
def delete_skill_file(
    name: str, path: str, user: AuthenticatedUser, agent: str = "default"
) -> dict[str, str]:
    try:
        ok = storage.delete_skill_file(_root(agent), name, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="skill file not found")
    return {"deleted": path}


@app.delete("/agents/{agent}", tags=["Agent"])
def purge(agent: str, user: AuthenticatedUser) -> dict[str, bool]:
    return {"purged": storage.purge_agent(_root(agent))}
