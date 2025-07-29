FROM ghcr.io/astral-sh/uv:python3.13-bookworm

RUN groupadd -g 1001 appuser && useradd -m -u 1001 -g appuser appuser

WORKDIR /app
# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT []

RUN chown -R appuser:appuser /app
USER appuser
CMD ["fastapi", "run", "--host", "0.0.0.0", "app/main.py"]
