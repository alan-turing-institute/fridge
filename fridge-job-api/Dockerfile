FROM ghcr.io/astral-sh/uv:python3.13-bookworm

COPY . /app
WORKDIR /app
RUN uv sync --locked
CMD ["uv", "run", "fastapi", "run", "app/main.py"]
