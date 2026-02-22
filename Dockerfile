# Build Stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1-dev \
    libgomp1 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
# Leere Stub-Verzeichnisse erstellen, damit setuptools packages.find nicht fehlschlägt
COPY pyproject.toml .
RUN mkdir -p app config && \
    pip install --upgrade pip && \
    pip install --no-cache-dir .

# Runtime Stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime libs
# curl: benötigt für HEALTHCHECK
# libsndfile1: benötigt für soundfile/faster-whisper
# libgomp1: benötigt für numpy, ctranslate2 (OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libgomp1 \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Application Code
COPY . .

# CRITICAL: Fix PYTHONPATH for imports
ENV PYTHONPATH=/app

# Create non-root user and ensure data directory exists
RUN useradd -m arni && \
    mkdir -p /app/data && \
    chown -R arni:arni /app && \
    chmod 755 /app/data
USER arni

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:8000/health || exit 1

# Command
# Command
CMD ["uvicorn", "app.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
