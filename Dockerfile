# Dockerfile for Telegram Bot Security Improvements

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create app user for security
RUN useradd -r -s /bin/false -u 1001 appuser

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p data logs backups config && \
    chown -R appuser:appuser /app && \
    chmod 755 /app && \
    chmod 750 data logs backups

# Switch to non-root user
USER appuser

# No port exposure needed for Telegram bot
# HEALTHCHECK disabled for background service

# Run the application
CMD ["python", "main.py"]