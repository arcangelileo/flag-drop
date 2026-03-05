# ============================================================================
# FlagDrop - Multi-stage Docker build
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder - install dependencies in a virtual environment
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies needed for compiled Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Create a virtual environment for clean dependency isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies first (cached unless pyproject.toml changes).
# Copy source tree so hatchling can build the package, then install.
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Stage 2: Runtime - minimal image with only what's needed to run
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Metadata
LABEL maintainer="FlagDrop <hello@flagdrop.dev>"
LABEL description="FlagDrop - Feature flag management platform"
LABEL version="0.1.0"

# Install tini for proper PID 1 signal handling (zombie reaping, SIGTERM forwarding)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini curl && \
    rm -rf /var/lib/apt/lists/*

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy the virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user and group
RUN groupadd --gid 1000 flagdrop && \
    useradd --uid 1000 --gid flagdrop --shell /bin/bash --create-home flagdrop

# Set working directory
WORKDIR /app

# Copy application source code
COPY --chown=flagdrop:flagdrop src/ ./src/
COPY --chown=flagdrop:flagdrop alembic/ ./alembic/
COPY --chown=flagdrop:flagdrop alembic.ini ./alembic.ini
COPY --chown=flagdrop:flagdrop pyproject.toml ./pyproject.toml

# Create data directory for SQLite database with correct ownership
RUN mkdir -p /app/data && chown flagdrop:flagdrop /app/data

# Expose the application port
EXPOSE 8000

# Switch to non-root user
USER flagdrop

# Default environment variables
ENV FLAGDROP_HOST="0.0.0.0" \
    FLAGDROP_PORT="8000" \
    FLAGDROP_DATABASE_URL="sqlite+aiosqlite:///./data/flagdrop.db" \
    FLAGDROP_DEBUG="false" \
    PYTHONPATH="/app/src"

# Signal for graceful shutdown
STOPSIGNAL SIGTERM

# Health check using curl for reliability
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use tini as init process for proper signal handling
ENTRYPOINT ["tini", "--"]

# Run Alembic migrations then start the server.
# Alembic's env.py reads FLAGDROP_DATABASE_URL and converts it to a sync URL.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host ${FLAGDROP_HOST} --port ${FLAGDROP_PORT} --timeout-graceful-shutdown 30"]
