# ============================================
# FastAPI Panama Papers Application Dockerfile
# ============================================
# Base image: Python 3.11 slim for smaller size
FROM python:3.11-slim

# Set metadata labels
LABEL maintainer="Panama Papers Project"
LABEL description="FastAPI application for Panama Papers Neo4j analysis"

# Set environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1
# Set Python path
ENV PYTHONPATH=/app

# Install system dependencies
# curl is required for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size
# --upgrade ensures latest compatible versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
# This is done after pip install for better Docker layer caching
COPY app/ ./app/

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Health check configuration
# Checks if the application is responding every 30 seconds
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the FastAPI application with Uvicorn
# --host 0.0.0.0 allows external connections
# --port 8000 matches the exposed port
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]