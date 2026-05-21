FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS builder

WORKDIR /app
# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
COPY . /app
RUN uv sync --locked --no-editable
# Sync the project
# --mount=type=cache,target=/root/.cache/uv \

# Place executables in the environment at the front of the path
FROM python:3.13-slim-bookworm
RUN groupadd -g 1001 appuser && useradd -m -u 1001 -g appuser appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuseer /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER appuser
CMD ["fastapi", "run", "--host", "0.0.0.0", "app/main.py"]
