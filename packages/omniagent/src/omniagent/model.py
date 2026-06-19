"""模型层:经 OpenAI 兼容端点(如 litellm 网关)接入。

端点暴露标准 OpenAI ``/v1`` API,故用 :class:`langchain_openai.ChatOpenAI` 直接对接,
无需各家厂商 SDK。``create_deep_agent`` 接受任意
:class:`~langchain_core.language_models.BaseChatModel` 实例。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from omniagent.config import Settings, export_openai_env, get_settings


def build_model(
    settings: Settings | None = None,
    *,
    model: str | None = None,
) -> ChatOpenAI:
    """构建指向 OpenAI 兼容端点的聊天模型。

    Args:
        settings: 覆盖默认配置;为空则调用 :func:`~omniagent.config.get_settings`。
        model: 覆盖 ``settings.model`` 的模型名(便于子代理/回退指定不同模型)。

    Returns:
        已配置 ``base_url`` / ``api_key`` / ``model`` / ``temperature`` 的
        :class:`~langchain_openai.ChatOpenAI`。
    """
    settings = settings or get_settings()
    # 让同进程内的其他 OpenAI 兼容组件(embeddings 等)也走同一网关。
    export_openai_env(settings)
    return ChatOpenAI(
        model=model or settings.model,
        base_url=settings.base_url,
        api_key=SecretStr(settings.api_key),
        temperature=settings.temperature,
        max_retries=settings.model_max_retries,
    )
