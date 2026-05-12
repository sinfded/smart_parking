FROM python:3.11-slim

# System deps for OpenCV and MQTT
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv sync --no-dev --extra api

COPY gateway/ gateway/

CMD ["uv", "run", "python", "-m", "gateway.main"]
