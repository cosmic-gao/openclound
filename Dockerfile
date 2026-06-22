FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /bin/uv

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
