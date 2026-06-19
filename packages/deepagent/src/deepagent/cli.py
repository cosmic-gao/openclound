"""交互式命令行(类 Claude Code):token 级流式输出 + 工具可视化 + 多轮记忆 + HITL 审批。

用法::

    deepagent                      # 进入交互式 REPL
    deepagent "refactor foo.py"    # 单次任务后退出
    deepagent --hitl               # 高危工具(写文件 / shell)执行前人工确认
    deepagent --mcp servers.json   # 额外挂载 MCP 工具
    deepagent --model claude-sonnet-4-6 --workspace ./.agent

REPL 内命令:``/exit`` 退出 · ``/reset`` 开新会话 · ``/help`` 帮助。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from deepagent import __version__

_BANNER = "deepagent · openclound deep agent (Claude Code-style)"
_PROMPT = "\n\033[1;36myou ›\033[0m "
_AGENT_TAG = "\n\033[1;32magent ›\033[0m "

# 是否正处于"流式打印 AI 文本"的行内状态(用于在打印工具调用前补换行)。
_stream_open = False


# ————————————————————————— 输出渲染 —————————————————————————


def _text(content: Any) -> str:
    """从消息 content(str 或内容块列表)提取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _short(value: Any, limit: int = 160) -> str:
    """把任意值压成单行短字符串,便于展示工具入参 / 结果。"""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _stream_text(delta: str) -> None:
    """流式输出 AI 文本增量(必要时先打印 ``agent ›`` 前缀)。"""
    global _stream_open
    if not delta:
        return
    if not _stream_open:
        sys.stdout.write(_AGENT_TAG)
        _stream_open = True
    sys.stdout.write(delta)
    sys.stdout.flush()


def _end_line() -> None:
    """结束当前流式文本行(若有)。"""
    global _stream_open
    if _stream_open:
        sys.stdout.write("\n")
        sys.stdout.flush()
        _stream_open = False


def _print_tool_call(call: dict[str, Any]) -> None:
    _end_line()
    name = call.get("name", "?")
    print(f"  \033[33m⚙ {name}\033[0m({_short(call.get('args', {}))})")


def _print_tool_result(msg: Any) -> None:
    _end_line()
    status = getattr(msg, "status", "success")
    mark = "\033[31m✗\033[0m" if status == "error" else "\033[90m↳\033[0m"
    print(f"  {mark} {_short(getattr(msg, 'content', ''))}")


# ————————————————————————— HITL 审批 —————————————————————————


def _ask_decisions(request: dict[str, Any]) -> list[dict[str, Any]]:
    """就一次中断里的待执行工具逐个询问用户,返回 decisions 列表。"""
    decisions: list[dict[str, Any]] = []
    for action in request.get("action_requests", []):
        name = action.get("name", "?")
        args = _short(action.get("args", {}), limit=400)
        print(f"\n\033[1;35m⚠ approval needed\033[0m {name}({args})")
        try:
            choice = (
                input("  allow? [y=yes / n=no / e=no with reason] ").strip().lower()
            )
        except (EOFError, KeyboardInterrupt):
            choice = "n"
        if choice == "y":
            decisions.append({"type": "approve"})
        elif choice == "e":
            try:
                reason = input("  reason (sent to the model): ").strip()
            except (EOFError, KeyboardInterrupt):
                reason = ""
            decisions.append(
                {"type": "reject", "message": reason or "User rejected the action."}
            )
        else:
            decisions.append({"type": "reject", "message": "User rejected the action."})
    return decisions


# ————————————————————————— 运行单轮 —————————————————————————


async def _run_turn(
    agent: Any, payload: Any, config: dict[str, Any]
) -> dict[str, Any] | None:
    """流式执行一轮;命中 HITL 中断时返回中断请求,否则返回 None。

    同时订阅 ``messages``(token 级 AI 文本)与 ``updates``(工具调用 / 结果 /
    中断)两路流。
    """
    interrupt_request: dict[str, Any] | None = None
    async for mode, chunk in agent.astream(
        payload, config=config, stream_mode=["updates", "messages"]
    ):
        if mode == "messages":
            msg, _meta = chunk
            if msg.__class__.__name__.startswith("AI"):
                _stream_text(_text(getattr(msg, "content", "")))
            continue
        # mode == "updates"
        if "__interrupt__" in chunk:
            _end_line()
            interrupts = chunk["__interrupt__"]
            if interrupts:
                interrupt_request = getattr(interrupts[0], "value", None)
            continue
        for delta in chunk.values():
            if not isinstance(delta, dict):
                continue
            for msg in delta.get("messages", []) or []:
                cls = msg.__class__.__name__
                if cls.startswith("AI"):
                    # 文本已在 messages 流逐字打印;此处仅补充工具调用展示。
                    for call in getattr(msg, "tool_calls", None) or []:
                        _print_tool_call(call)
                elif cls.startswith("Tool"):
                    _print_tool_result(msg)
    _end_line()
    return interrupt_request


async def _converse(agent: Any, user_input: str, config: dict[str, Any]) -> None:
    """处理一条用户输入,含 HITL 中断 → 审批 → 恢复的循环。"""
    from langgraph.types import Command

    payload: Any = {"messages": [{"role": "user", "content": user_input}]}
    while True:
        request = await _run_turn(agent, payload, config)
        if request is None:
            return
        decisions = _ask_decisions(request)
        payload = Command(resume={"decisions": decisions})


# ————————————————————————— 组装 / 入口 —————————————————————————


def _apply_env(args: argparse.Namespace) -> None:
    """把命令行开关写入 ``AGENT_*`` 环境变量(须在 get_settings 之前)。"""
    if args.model:
        os.environ["AGENT_MODEL"] = args.model
    if args.workspace:
        os.environ["AGENT_WORKSPACE"] = args.workspace
    if args.no_shell:
        os.environ["AGENT_ENABLE_SHELL"] = "0"
    if args.hitl:
        os.environ["AGENT_ENABLE_HITL"] = "1"


def _load_mcp(path: str | None) -> dict[str, dict[str, Any]] | None:
    """从 JSON 文件读取 MCP server 配置。"""
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # 兼容 {"mcpServers": {...}} 与直接 {...} 两种写法。
    servers = data.get("mcpServers", data) if isinstance(data, dict) else data
    return servers or None


async def _build(args: argparse.Namespace) -> Any:
    from deepagent import build_agent, build_async_agent

    servers = _load_mcp(args.mcp)
    if servers:
        return await build_async_agent(mcp_servers=servers, managed_checkpointer=True)
    return build_agent(managed_checkpointer=True)


async def _amain(args: argparse.Namespace) -> int:
    _apply_env(args)

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "\033[33mwarning:\033[0m OPENAI_API_KEY not set; "
            "connecting to the gateway with a placeholder key may fail.",
            file=sys.stderr,
        )

    try:
        agent = await _build(args)
    except Exception as exc:  # noqa: BLE001 — 顶层入口,友好报错
        print(f"\033[31mfailed to build agent:\033[0m {exc}", file=sys.stderr)
        return 1

    config: dict[str, Any] = {"configurable": {"thread_id": args.thread}}

    # 单次任务模式
    if args.prompt:
        await _converse(agent, args.prompt, config)
        print()
        return 0

    # 交互式 REPL
    print(f"\033[1m{_BANNER}\033[0m  (v{__version__})")
    print("Type a task to start; /help for commands, /exit to quit.")
    while True:
        try:
            user_input = input(_PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return 0
        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            print("bye.")
            return 0
        if user_input == "/help":
            print("commands: /exit quit · /reset new session · /help this help")
            continue
        if user_input == "/reset":
            config = {"configurable": {"thread_id": os.urandom(4).hex()}}
            print("started a new session.")
            continue
        try:
            await _converse(agent, user_input, config)
        except KeyboardInterrupt:
            _end_line()
            print("\033[33minterrupted.\033[0m")
        except Exception as exc:  # noqa: BLE001 — REPL 不因单轮出错而退出
            _end_line()
            print(f"\033[31merror:\033[0m {exc}")


def main(argv: list[str] | None = None) -> int:
    """CLI 入口(``deepagent`` 命令)。"""
    # 确保 Windows 等终端能正确渲染 UTF-8 / ANSI 输出。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="deepagent", description=_BANNER)
    parser.add_argument(
        "prompt", nargs="?", help="one-shot task; omit to start the interactive REPL"
    )
    parser.add_argument(
        "--model", help="override the model name (default: AGENT_MODEL)"
    )
    parser.add_argument("--workspace", help="workspace directory (default: .agent)")
    parser.add_argument("--mcp", help="path to an MCP servers JSON config file")
    parser.add_argument(
        "--thread", default="cli", help="session thread_id (for multi-turn memory)"
    )
    parser.add_argument(
        "--hitl", action="store_true", help="ask for approval before high-risk tools"
    )
    parser.add_argument(
        "--no-shell", action="store_true", help="disable the shell tool"
    )
    parser.add_argument(
        "--version", action="version", version=f"deepagent {__version__}"
    )
    args = parser.parse_args(argv)

    try:
        return asyncio.run(_amain(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
