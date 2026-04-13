FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create persistent data directory and uploads
RUN mkdir -p /data /data/uploads

# Expose port
EXPOSE ${PORT:-8000}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')"

# Default env: store DB and uploads on the persistent volume
ENV MAZARINE_DB_PATH=/data/mazarine.db
ENV MAZARINE_UPLOAD_DIR=/data/uploads

# Run
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
