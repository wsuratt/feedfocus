# Multi-stage build for optimized production image

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Accept environment variables as build args
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_API_URL

# Make them available during build
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
ENV VITE_API_URL=$VITE_API_URL

# Debug: Print to verify (remove after testing)
RUN echo "Build args check:" && \
    echo "VITE_SUPABASE_URL=$VITE_SUPABASE_URL" && \
    echo "VITE_API_URL=$VITE_API_URL" && \
    echo "Has ANON_KEY=$([ -n "$VITE_SUPABASE_ANON_KEY" ] && echo 'YES' || echo 'NO')"

COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend runtime
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for backend and Playwright/Chromium
RUN apt-get update && apt-get install -y \
    gcc \
    wget \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (backend only - no heavy automation packages)
COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

# Install Playwright browsers for crawl4ai
RUN crawl4ai-setup

# Set environment variable to suppress tokenizers parallelism warning
ENV TOKENIZERS_PARALLELISM=false

# Copy application code
COPY automation/ ./automation/
COPY backend/ ./backend/
COPY db/ ./db/
COPY .env.example ./.env

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Initialize database
RUN python db/init_db.py || true

# Apply performance indexes migration
RUN python db/apply_migration.py 003_performance_indexes.sql || true

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/')"

# Run application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
