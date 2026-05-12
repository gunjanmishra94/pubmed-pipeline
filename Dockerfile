FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_SYSTEM_PYTHON=1 \
    PYTHONUNBUFFERED=1 \
    DAGSTER_HOME=/app \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN mkdir -p /app/data

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY workspace.yaml dagster.yaml ./

ENV PYTHONPATH=/app/src
