"""基础冒烟测试:仅验证包可导入、入口可用,不真正调用模型。"""

from __future__ import annotations

import os


def test_package_metadata() -> None:
    import deepagent

    assert deepagent.__version__ == "0.1.0"
    assert callable(deepagent.build_agent)


def test_build_agent_constructs() -> None:
    # 构建期不会真正调用模型;设置占位 key 以满足 ChatAnthropic 初始化。
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-placeholder")

    from deepagent import build_agent

    agent = build_agent()
    assert hasattr(agent, "invoke")
