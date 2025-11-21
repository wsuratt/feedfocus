#!/bin/bash
# Build frontend for deployment

set -e

echo "📦 Building frontend..."

cd frontend

# Install dependencies
npm ci

# Build for production
npm run build

echo "✅ Frontend built successfully!"
echo "📁 Output: frontend/dist"
