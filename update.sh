#!/bin/bash
set -e

# --- Resolve absolute paths based on script location ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR"
FRONTEND_DIR="$SCRIPT_DIR/../mousetube_frontend"

# --- 1️⃣ Pull latest code ---
echo "🔄 Updating backend..."
cd "$BACKEND_DIR"
git pull origin main

echo "🔄 Updating frontend..."
cd "$FRONTEND_DIR"
git pull origin main

# --- 2️⃣ Build and restart Docker containers ---
echo "🐳 Building and restarting Docker containers..."
cd "$BACKEND_DIR"
docker compose -f docker-compose.prod.yml up -d --build

# --- 3️⃣ Clean up Docker (optional, frees space) ---
echo "🧹 Cleaning up Docker..."
docker container prune -f
docker image prune -af
docker builder prune -f

echo "✅ Backend and frontend updated, containers rebuilt, migrations applied, cleanup done!"