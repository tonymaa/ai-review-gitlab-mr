# GitLab AI Review - Web Dockerfile
# Multi-stage build: Build frontend -> Setup backend -> Final image

# ==================== Stage 1: Build Frontend ====================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# Copy package files
COPY web/package.json web/package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY web/ ./

# Build the frontend
RUN npm run build

# ==================== Stage 2: Python Dependencies ====================
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ==================== Stage 3: Final Image ====================
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from backend-builder
COPY --from=backend-builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy backend source code
COPY server/ ./server/
COPY src/ ./src/
COPY server.py ./
COPY config.yaml ./
COPY config.example.yaml ./
COPY .env.example ./.env

# Copy built frontend from frontend-builder
COPY --from=frontend-builder /app/web/dist ./web/dist

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create necessary directories
RUN mkdir -p cache data logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 19000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:19000/api/health')" || exit 1

# Entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Start the server
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "19000"]
