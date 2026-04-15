# QUAN Recovery API Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md alembic.ini ./
COPY quan/ ./quan/
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir .

# Production image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r quan && useradd -r -g quan quan

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY quan/ ./quan/
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/
COPY alembic.ini README.md ./

# Set ownership
RUN chown -R quan:quan /app

USER quan

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/livez || exit 1

# Run application
CMD ["uvicorn", "quan.main:app", "--host", "0.0.0.0", "--port", "8000"]
