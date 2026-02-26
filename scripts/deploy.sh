#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not on PATH" >&2
  exit 1
fi

if [[ ! -f "docker-compose.yml" ]]; then
  echo "docker-compose.yml not found. Run this script from the repository root." >&2
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo ".env not found. Create it before deploying." >&2
  exit 1
fi

echo "Starting data services (redis, postgres, qdrant)..."
docker compose up -d redis postgres qdrant

echo "Running Alembic migrations..."
docker compose run --rm api alembic upgrade head

echo "Building and starting API..."
docker compose up -d --build api

echo "Deployment complete. Current service status:"
docker compose ps
