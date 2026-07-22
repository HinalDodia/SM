# ─── Backend Dockerfile ───────────────────────────────────────────────────────
# Multi-stage build for a production-ready Flask backend.
# Usage:
#   docker build -t sm-backend .
#   docker run -p 5000:5000 --env-file .env sm-backend
FROM python:3.12-slim

WORKDIR /app

# Install system deps (needed for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer cache)
COPY invest/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set Python path so Endpoints package is importable
ENV PYTHONPATH=/app

EXPOSE 5000

# Use gunicorn for production (single-threaded dev: python run.py)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "run:app"]
