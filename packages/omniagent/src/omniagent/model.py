"""模型层:经 OpenAI 兼容端点(litellm 网关等)接入 ``ChatOpenAI``。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from omniagent.config import Settings, export_openai_env, get_settings


def build_model(
    settings: Settings | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> ChatOpenAI:
    """构建指向 OpenAI 兼容端点的聊天模型(``model`` / ``temperature`` 可覆盖)。"""
    settings = settings or get_settings()
    export_openai_env(settings)  # 让 embeddings 等也走同一网关
    return ChatOpenAI(
        model=model or settings.model,
        base_url=settings.base_url,
        api_key=SecretStr(settings.api_key),
        temperature=temperature if temperature is not None else settings.temperature,
        max_retries=settings.model_max_retries,
    )
