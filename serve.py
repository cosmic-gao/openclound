"""Windows 本地启动入口。

LangGraph 的 Postgres checkpointer/store 用 psycopg,psycopg 异步在 Windows 必须用
SelectorEventLoop。而 uvicorn 在 Windows 硬编码 ProactorEventLoop(loops/asyncio.py),
会覆盖它导致连接池超时;故显式建 SelectorEventLoop 并以 loop="none" 启动 uvicorn。
生产 Docker(Linux)无此冲突,仍用 `aegra serve`。

    uv run python serve.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_ROOT = Path(__file__).parent
os.environ.setdefault("AEGRA_CONFIG", str(_ROOT / "aegra.json"))
load_dotenv(_ROOT / ".env")


async def _serve() -> None:
    import uvicorn

    # loop="none":沿用上面的 SelectorEventLoop,不让 uvicorn 切回 Proactor
    config = uvicorn.Config(
        "aegra_api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "2026")),
        loop="none",
    )
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    asyncio.run(_serve())
