FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS builder

# uv 经 pip 安装(避开 ghcr.io 拉取不稳定)。PyPI 源经 build-arg PIP_INDEX_URL 注入
# (默认官方源,可在 .env 覆盖);pip 与 uv 共用同一源。
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    UV_INDEX_URL=${PIP_INDEX_URL}
RUN pip install --no-cache-dir uv==0.10.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY uv.loc[k] ./
RUN uv sync --no-dev --no-install-project --compile-bytecode
COPY src/ ./src/
COPY README.md ./
RUN uv sync --no-dev --compile-bytecode

FROM base AS final

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY aegra.json .
COPY src/ ./src/
RUN mkdir -p /app/.agent && chown -R app:app /app/.agent  # 工作区需可写(named volume 继承属主)

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 2026
USER app
CMD ["aegra", "serve"]
