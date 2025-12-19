FROM python:3.11-slim-bookworm

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install system dependencies
# chromium: for selenium
# chromium-driver: driver for chromium
# curl: general utility
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# --frozen: Sync with uv.lock
# --no-dev: Do not install dev dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Set environment variables
# PYTHONPATH: ensure python can find the package
ENV PYTHONPATH=/app
# PATH: ensure the virtualenv's bin is in PATH
ENV PATH="/app/.venv/bin:$PATH"
# PYTHONUNBUFFERED: ensure logs appear immediately (not buffered)
ENV PYTHONUNBUFFERED=1

# Disable UV telemetry (prevents Plausible analytics errors in logs)
ENV UV_NO_ANALYTICS=1

# Chrome/Chromium environment variables for Docker
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROME_DRIVER=/usr/bin/chromedriver
# Disable Chrome sandbox (required for running as root in Docker)
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage"

# Entrypoint
# We assume the user wants to run the fetch command by default
ENTRYPOINT ["python", "cli.py"]
CMD ["fetch"]
