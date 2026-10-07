# ------------------------------------------------------------------------------
# Stage 1: Build virtual environment with uv
# ------------------------------------------------------------------------------
FROM python:3.14-slim AS builder

# Install uv from the official Astral uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation and copy link mode for reproducible, fast builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy dependency definition files first to leverage Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Install only production dependencies (excluding dev dependency groups)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ------------------------------------------------------------------------------
# Stage 2: Production runtime image
# ------------------------------------------------------------------------------
FROM python:3.14-slim AS runner

# Environment variables:
# - PYTHONUNBUFFERED=1: Stream logs directly without buffering
# - PYTHONDONTWRITEBYTECODE=1: Prevent writing bytecode at runtime (already compiled)
# - PATH: Prepend virtual environment binaries to PATH
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Create a dedicated non-root user and group for security
RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --uid 10001 --gid appgroup --create-home --no-log-init appuser

# Set working directory
WORKDIR /app

# Pre-create directory for rotating logs with non-root write permissions
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

# Copy application source code and configurations
COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup README.md pyproject.toml .env.example /app/

# Switch to non-root user
USER appuser

# Entrypoint executes the interactive CLI turn runner
ENTRYPOINT ["python", "-m", "app.cli"]
