# Multi-stage Dockerfile for production Django LMS

# Stage 1: Build stage for Node.js dependencies and TailwindCSS
FROM node:20-slim AS frontend-builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install Node dependencies
RUN npm install

# Copy TailwindCSS config and source files
COPY tailwind.input.css ./
# COPY static ./static
COPY freedom_ls ./freedom_ls

# Build TailwindCSS for production
RUN npm run tailwind_build


# Stage 2: Python dependencies and application
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create app directory and user
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY --chown=appuser:appuser pyproject.toml ./

# Install Python dependencies (production only, no dev dependencies)
RUN uv pip install --system -r pyproject.toml && \
    uv pip install --system gunicorn

# Copy application code
COPY --chown=appuser:appuser . .

# Copy built TailwindCSS from frontend-builder
COPY --from=frontend-builder --chown=appuser:appuser /app/static/vendor/tailwind.output.css /app/static/vendor/tailwind.output.css

# Copy and setup entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user for collectstatic
USER appuser

ENV DJANGO_SETTINGS_MODULE=config.settings_prod

# Collect static files
RUN python manage.py collectstatic --noinput 

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health/', timeout=2)" || exit 1

# Switch back to root for entrypoint (will switch to appuser inside entrypoint)
USER root

# Set entrypoint to handle permissions
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Run gunicorn
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
