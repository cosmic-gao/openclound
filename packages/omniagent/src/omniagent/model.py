"""模型层:统一经 ``langchain_openai`` 接入所有模型 / 第三方网关(无默认,连接必填)。"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr


def build_model(
    *,
    model: str | None,
    base_url: str | None,
    api_key: str | None,
    temperature: float | None = None,
    model_params: dict[str, Any] | None = None,
    max_retries: int = 2,
) -> ChatOpenAI:
    """构造 :class:`ChatOpenAI`;缺 ``model``/``base_url``/``api_key`` 任一即报错。

    ``temperature`` / ``model_params`` 仅在显式提供时透传。
    """
    missing = [
        name
        for name, value in (
            ("model", model),
            ("base_url", base_url),
            ("api_key", api_key),
        )
        if not value
    ]
    if missing:
        msg = f"assistant must assign {' + '.join(missing)} (no defaults)"
        raise ValueError(msg)
    assert model is not None and base_url is not None and api_key is not None

    kwargs: dict[str, Any] = {
        "model": model,
        "base_url": base_url,
        "api_key": SecretStr(api_key),
        "max_retries": max_retries,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if model_params:
        kwargs.update(model_params)
    return ChatOpenAI(**kwargs)
