#!/bin/bash
# Build all Docker images for the helmet system

set -e

echo "Building Helmet OS Docker images..."

# Build base image first
echo "Building base image..."
docker build -f deploy/docker/Dockerfile.base -t helmet-base:latest .

# Build service images
echo "Building video service..."
docker build -f deploy/docker/Dockerfile.video -t helmet-video:latest .

echo "Building perception service..."
docker build -f deploy/docker/Dockerfile.perception -t helmet-perception:latest .

echo "Building voice service..."
docker build -f deploy/docker/Dockerfile.voice -t helmet-voice:latest .

echo "Building orchestrator service..."
docker build -f deploy/docker/Dockerfile.orchestrator -t helmet-orchestrator:latest .

echo "Building UI service..."
docker build -f deploy/docker/Dockerfile.ui -t helmet-ui:latest .

echo "Building development tools..."
docker build -f deploy/docker/Dockerfile.dev -t helmet-dev:latest .

echo "Build complete!"
echo ""
echo "To start the system:"
echo "  docker-compose up"
echo ""
echo "To start with development tools:"
echo "  docker-compose --profile dev up"