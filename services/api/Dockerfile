# ============================================================
# QuantifyU API — Production Dockerfile
# Build context: project root (quantifyu/)
# ============================================================

FROM python:3.11-slim AS base

# System deps for OpenCV, MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY services/api/ .

# Create model directory
RUN mkdir -p /app/app/ai/models

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "app.main:app", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
