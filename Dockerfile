# Multi-stage build for Research Data Management PaaS
FROM python:3.11-slim as builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev

# Production stage
FROM python:3.11-slim as production

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY agent/ ./agent/
COPY paas_api_with_auth.py ./
COPY enhanced_rag_interface.py ./
COPY rag_interface.py ./
COPY config.py ./
COPY data/ ./data/

# Create non-root user
RUN groupadd -r paas && useradd -r -g paas -d /app -s /bin/bash paas
RUN chown -R paas:paas /app
USER paas

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "paas_api_with_auth.py"]