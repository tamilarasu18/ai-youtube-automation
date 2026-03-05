# ============================================================
# AI Shorts Engine — Multi-Stage Dockerfile
# ============================================================
# Requires: ffmpeg, Python 3.11+, GPU passthrough (optional)
# ============================================================

FROM python:3.11-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# ── Dependencies ────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application ─────────────────────────────────────────────
FROM deps AS app

COPY pyproject.toml .
COPY src/ src/

# Install the package itself
RUN pip install --no-cache-dir -e .

# Create required directories
RUN mkdir -p output logs config assets && \
    chown -R appuser:appuser /app

USER appuser

# Default command: start the API server
EXPOSE 8000
CMD ["video-engine", "serve", "--host", "0.0.0.0", "--port", "8000"]
