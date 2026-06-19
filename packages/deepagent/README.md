# deepagent

openclound 的 **deep agent 基础包**,封装 [LangChain `deepagents`](https://github.com/langchain-ai/deepagents):内置任务规划(`write_todos`)、虚拟文件系统、子代理(`task`)等能力,默认使用 **Claude Sonnet 4.6**。

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)(包 / 环境管理)
- 环境变量 `ANTHROPIC_API_KEY`(运行时调用 Claude 所需)

## 目录结构

```
packages/deepagent/
├── pyproject.toml          # uv_build 构建后端 + ruff/mypy/pytest 配置
├── README.md
├── src/
│   └── deepagent/
│       ├── __init__.py
│       ├── agent.py        # build_agent() 入口
│       └── py.typed        # PEP 561 内联类型标记
└── tests/
    └── test_smoke.py
```

## 开发

```bash
# 在包目录内(或从仓库根加 --directory packages/deepagent)
uv sync                 # 创建 .venv 并安装依赖(含 dev 组)
uv run pytest           # 运行测试
uv run ruff check .     # lint
uv run ruff format .    # 格式化
uv run mypy src         # 类型检查
```

## 用法

```python
import os
from deepagent import build_agent

os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

def search(query: str) -> str:
    """A simple search tool."""
    return f"results for {query}"

agent = build_agent(tools=[search])
result = agent.invoke({"messages": [{"role": "user", "content": "调研 LangGraph 并总结"}]})
print(result["messages"][-1].content)
```

子代理:

```python
agent = build_agent(subagents=[{
    "name": "researcher",
    "description": "用于深入调研子问题",
    "system_prompt": "你是严谨的研究员。",
}])
```

> 基于 deepagents `>=0.6.11`。注意该库近期已将 `instructions` 参数更名为 `system_prompt`。
