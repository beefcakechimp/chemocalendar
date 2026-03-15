FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for DB volume and temp files
# /data is the mount point for persistent storage
# /tmp is used for DOCX export temp files
RUN mkdir -p /data /tmp/chemocal

# Non-root user for security (Railway/Fly.io best practice)
RUN adduser --disabled-password --no-create-home appuser \
    && chown -R appuser:appuser /data /tmp/chemocal /app
USER appuser

EXPOSE 8000

# Use $PORT if provided (Railway), else default 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]